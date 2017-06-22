# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import inspect
import logging
import datetime
import json
from genshi.template import NewTextTemplate

from sql import Union, Column, Literal, Window, Null
from sql.aggregate import Max
from sql.conditionals import Coalesce

from contextlib import contextmanager

from trytond.model import Model, ModelView, ModelSQL, fields as tryton_fields
from trytond.model import UnionMixin as TrytonUnionMixin, Unique
from trytond.exceptions import UserError
from trytond.pool import Pool, PoolMeta
from trytond.cache import Cache
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.wizard import Wizard, StateAction
from trytond.tools import reduce_ids, cursor_dict, memoize
from trytond.config import config

import fields
import export
import summary
import types

try:
    import async.broker as async_broker
    if config.get('async', 'celery', default=None) is not None:
        async_broker.set_module('celery')
    elif config.get('async', 'rq', default=None) is not None:
        async_broker.set_module('rq')
    else:
        raise Exception('no async broker')
except Exception:
    async_broker = None


_dictionarize_fields_cache = Cache('dictionarize_fields', context=False)

__all__ = [
    'error_manager',
    'FunctionalErrorMixIn',
    'CoogSQL',
    'CoogView',
    'CoogWizard',
    'expand_tree',
    'UnionMixin',
    'TaggedMixin',
    'MethodDefinition',
    ]


class PostExecutionDataManager(object):

    _instance = None
    queue = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = object.__new__(cls)
        return cls._instance

    def put(self, func, *args, **kwargs):
        self.queue.append((func, args, kwargs))

    def abort(self, trans):
        self._finish()

    def tpc_begin(self, trans):
        pass

    def commit(self, trans):
        pass

    def tpc_vote(self, trans):
        pass

    def tpc_finish(self, trans):
        """
        Post commit function execution.
        Function must never do C(reate)U(pdate)D(elete) operations
        """
        with Transaction().new_transaction(readonly=True):
            for fct, args, kwargs in self.queue:
                fct(*args, **kwargs)
        self._finish()

    def tpc_abort(self, trans):
        self._finish()

    def _finish(self):
        self.queue = []


class BrokerCheckDataManager(PostExecutionDataManager):

    def tpc_begin(self, trans):
        assert async_broker
        async_broker.get_module().connection.ping()


def post_transaction(DataManager=PostExecutionDataManager):
    '''
    The decorated method will be executed AFTER the commit of the current
    transaction.
    It will be also executed in a readonly transaction so you must never write
    code which may do update / write operations.
    '''
    def wrapper(func):
        assert (isinstance(func, types.UnboundMethodType)
            or isinstance(func, types.FunctionType)), type(func)

        def decorate(*args, **kwargs):
            transaction = Transaction()
            datamanager = transaction.join(DataManager())
            datamanager.put(func, *args, **kwargs)
            return True

        return decorate
    return wrapper


def genshi_evaluated_fields(*fields_):
    # Do the magic

    @memoize(1000)
    def cached_text_template(to_evaluate):
        return NewTextTemplate(to_evaluate)

    def evaluate_string(context_, to_evaluate):
        tmpl = cached_text_template(to_evaluate)
        evaluated_field = tmpl.generate(**context_).render()
        return evaluated_field

    def get_evaluated_field(self, name):
        original_field_value = getattr(self, '_'.join(name.split('_')[2:]))
        genshi_context = self.get_genshi_context([self], name) if hasattr(
            self, 'get_genshi_context') else {}
        return evaluate_string(genshi_context, original_field_value or '')

    @classmethod
    def get_genshi_context(cls, records, field_name):
        return ServerContext().get('genshi_context', {})

    def decorate(klass):
        for field_ in fields_:
            evaluated_field_name = 'genshi_evaluated_' + field_
            original_field = getattr(klass, field_)
            setattr(klass, evaluated_field_name, fields.Function(
                    fields.Char(original_field.string + ' Genshi Evaluated'),
                    loader='get_genshi_evaluated'))
            setattr(klass, 'get_genshi_evaluated', get_evaluated_field)
        setattr(klass, 'get_genshi_context', get_genshi_context)
        return klass
    return decorate


def dictionarize(instance, field_names=None, set_rec_names=False):
    '''
        Returns a dict which may be used to initialize a copy of instance with
        with identical field values than those of the base instance.

          - field_names : If not set, will try to recursively get all all
            fields. If a list, only those fields will be handled (ids for
            One2Many fields). If a dict, the keys will be models and the values
            will be the list of fields to extract for the model.

          - set_rec_names : If True, Many2One and Reference fields will have
            their rec_name in the resulting dict, to avoir extra reads from the
            client.
    '''
    if field_names is None:
        field_names = get_dictionarize_fields(instance.__class__)
    if isinstance(field_names, (list, tuple)):
        field_names = {instance.__name__: field_names}
    if not field_names.get(instance.__name__, None):
        return instance.id
    res = {fname: getattr(instance, fname, None)
        for fname in field_names[instance.__name__]}
    for k, v in res.iteritems():
        if isinstance(v, Model):
            res[k] = v.id
            if isinstance(instance._fields[k], tryton_fields.Reference):
                res[k] = '%s,%s' % (v.__name__, v.id)
            if set_rec_names:
                res[k + '.rec_name'] = getattr(v, 'rec_name', '')
        elif isinstance(v, (list, tuple)):
            res[k] = [dictionarize(x, field_names, set_rec_names) for x in v]
    return res


def get_dictionarize_fields(model):
    vals = _dictionarize_fields_cache.get(model.__name__, None)
    if vals is not None:
        return vals
    pool = Pool()
    res = {model.__name__: []}
    for fname, field in model._fields.iteritems():
        if (isinstance(field, tryton_fields.Function) and not
                isinstance(field, tryton_fields.Property)):
            continue
        res[model.__name__].append(fname)
        if isinstance(field, tryton_fields.One2Many):
            res.update(get_dictionarize_fields(pool.get(field.model_name)))
            # Remove parent field
            if field.field:
                res[field.model_name].pop(field.field)
    _dictionarize_fields_cache.set(model.__name__, res)
    return res


class ErrorManager(object):
    'Error Manager class, which stores non blocking errors to be able to raise'
    'them together'
    def __init__(self):
        self._errors = []
        self._error_messages = []

    def add_error(self, error_message, error=None, error_args=None, fail=True):
        'Add a new error to the current error list. If fail is set, the error'
        'will trigger the error raising when exiting the manager.'
        self._errors.append((error or error_message, error_args or (), fail))
        self._error_messages.append(error_message)

    def pop_error(self, error_code):
        for idx, cur_error in enumerate(self._errors):
            if cur_error[0] == error_code:
                break
        else:
            return False
        value = self._errors[idx]
        del self._errors[idx]
        del self._error_messages[idx]
        return value

    def format_errors(self):
        return '\n'.join(self._error_messages)

    @property
    def _do_raise(self):
        return any([x[2] for x in self._errors])

    def raise_errors(self):
        if self._do_raise:
            raise UserError(self.format_errors())


@contextmanager
def error_manager():
    manager = ErrorManager()
    with ServerContext().set_context(error_manager=manager):
        try:
            yield
        except UserError, exc:
            manager.add_error(exc.message)
        finally:
            manager.raise_errors()


class FunctionalErrorMixIn(object):
    @classmethod
    def append_functional_error(cls, error, error_args=None, fail=True):
        error_manager = ServerContext().get('error_manager', None)
        if error_manager is None:
            return cls.raise_user_error(error, error_args)
        error_message = cls.raise_user_error(error, error_args,
            raise_exception=False)
        error_manager.add_error(error_message, error, error_args, fail)

    @classmethod
    def pop_functional_error(cls, error_code):
        manager = ServerContext().get('error_manager', None)
        if not manager:
            return False
        return manager.pop_error(error_code)

    @property
    def _error_manager(self):
        return ServerContext().get('error_manager', None)


class CoogSQL(export.ExportImportMixin, FunctionalErrorMixIn,
        summary.SummaryMixin):
    create_date_ = fields.Function(
        fields.DateTime('Creation date'),
        '_get_creation_date')

    @classmethod
    def __post_setup__(cls):
        super(CoogSQL, cls).__post_setup__()
        if cls.table_query != ModelSQL.table_query:
            return
        if cls._table and len(cls._table) > 64:
            logging.getLogger(__name__).warning('Length of table_name' +
                ' > 64 => ' + cls._table)
        pool = Pool()
        for field_name, field in cls._fields.iteritems():
            if isinstance(field, fields.Many2One):
                if getattr(field, '_on_delete_not_set', None):
                    logging.getLogger('fields').warning('Ondelete not set for'
                        ' field %s on model %s' % (field_name, cls.__name__))
            elif isinstance(field, fields.One2Many):
                target_model = pool.get(field.model_name)
                target_field = getattr(target_model, field.field)
                if target_field.required and not field._delete_missing:
                    logging.getLogger('fields').warning(
                        'Field %s of %s ' % (field_name, cls.__name__) +
                        'should probably have "delete_missing" set since ' +
                        'target field is required')
                if isinstance(target_field, tryton_fields.Function):
                    continue
                if target_model.table_query != ModelSQL.table_query:
                    continue
                if (not target_field.required and not
                        field._target_not_required):
                    logging.getLogger('fields').warning(
                        'Field %s of %s ' % (field.field, field.model_name) +
                        'should be required since it is used as a reverse ' +
                        'field for field %s of %s' % (
                            field_name, cls.__name__))
                if not target_field.select and not field._target_not_indexed:
                    logging.getLogger('fields').warning(
                        'Field %s of %s ' % (field.field, field.model_name) +
                        'should be selected since it is used as a reverse ' +
                        'field for field %s of %s' % (
                            field_name, cls.__name__))
            elif isinstance(field, tryton_fields.Property):
                if getattr(cls, 'default_' + field_name, None) is not None:
                    logging.getLogger('fields').warning(
                        'Field %s of %s ' % (field_name, field.model_name) +
                        'has a default method but it is useless since '
                        'Property fields ignore defaults')

    @property
    def _save_values(self):
        # This overrides serves two purposes :
        #   - Automatically convert removal to deletions for O2M fields
        #     according to the "delete_missing" attribute
        #   - Optimize writes by cleaning up empty write actions on O2M fields.
        #     No need to trigger a write for :
        #         [('write', [...], {'my_list': []})]
        values = super(CoogSQL, self)._save_values
        new_values = {}
        for fname, fvalues in values.iteritems():
            field = self._fields[fname]
            if isinstance(field, fields.One2Many) and not fvalues:
                continue
            new_values[fname] = fvalues
            if not isinstance(field, fields.One2Many):
                continue
            for idx, action in enumerate(fvalues):
                if not field._delete_missing:
                    continue
                if action[0] == 'remove':
                    fvalues[idx] = ('delete', action[1])
        return new_values

    def __getattr__(self, name):
        cls = self.__class__
        field = cls._fields.get(name, None)
        if isinstance(field, fields.Function) and field.loader:
            from inspect import getargspec
            func_loader = getattr(cls, field.loader)
            name_required = len(getargspec(func_loader).args) > 1
            if name_required:
                return getattr(cls, field.loader)(self, name)
            else:
                return getattr(cls, field.loader)(self)
        return super(CoogSQL, self).__getattr__(name)

    def __setattr__(self, name, value):
        cls = self.__class__
        field = cls._fields.get(name, None)
        super(CoogSQL, self).__setattr__(name, value)
        if isinstance(field, fields.Function) and field.updater:
            getattr(cls, field.updater)(self, value)

    @classmethod
    def update_values_before_create(cls, vlist):
        pass

    @classmethod
    def create(cls, vlist):
        cls.update_values_before_create(vlist)
        return super(CoogSQL, cls).create(vlist)

    @classmethod
    def delete(cls, instances):
        # Do not remove, needed to avoid infinite recursion in case a model
        # has a O2Ref which can lead to itself.
        if not instances:
            return
        # Handle O2M with fields.Reference backref
        to_delete = []
        for field_name, field in cls._fields.iteritems():
            if not isinstance(field, tryton_fields.One2Many):
                continue
            Target = Pool().get(field.model_name)
            backref_field = Target._fields[field.field]
            if not isinstance(backref_field, tryton_fields.Reference):
                continue
            to_delete.append((field.model_name, field.field))

        instance_list = ['%s,%s' % (i.__name__, i.id) for i in instances]
        super(CoogSQL, cls).delete(instances)
        for model_name, field_name in to_delete:
            TargetModel = Pool().get(model_name)
            TargetModel.delete(TargetModel.search(
                [(field_name, 'in', instance_list)]))

    @classmethod
    def _get_history_table(cls):
        '''
            This method returns a query that can be used as a substitute for
            the "real" table from an history point of view.

            The aim is to seemlessly replace __table__ in function fields
            (typical use case) which use queries.
        '''
        pool = Pool()
        ModelAccess = pool.get('ir.model.access')
        history_table = cls.__table_history__()

        # Mandatory, crash if not in context
        _datetime = Transaction().context.get('_datetime')
        assert _datetime

        columns = []
        for field_name in cls._fields.keys():
            field = cls._fields.get(field_name)
            if not field or hasattr(field, 'get'):
                continue
            if ModelAccess.check_relation(cls.__name__, field_name,
                    mode='read'):
                columns.append(field.sql_column(history_table).as_(field_name))

        window_id = Window([Column(history_table, 'id')])
        window_date = Window([Coalesce(history_table.write_date,
                    history_table.create_date)])
        columns.append(Column(history_table, '__id').as_('__id'))
        columns.append(Max(Coalesce(history_table.write_date,
                    history_table.create_date), window=window_id
                ).as_('__max_start'))
        columns.append(Max(Column(history_table, '__id'), window=window_date
                ).as_('__max__id'))

        if Transaction().context.get('_datetime_exclude', False):
            where = Coalesce(history_table.write_date,
                history_table.create_date) < _datetime
        else:
            where = Coalesce(history_table.write_date,
                history_table.create_date) <= _datetime

        tmp_table = history_table.select(*columns, where=where)
        return tmp_table.select(where=(
                (Column(tmp_table, '__max_start') == Coalesce(
                        tmp_table.write_date, tmp_table.create_date))
                & (Column(tmp_table, '__id') == Column(tmp_table, '__max__id'))
                # create_date = Null => Elem deleted
                & (tmp_table.create_date != Null)))

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        # Set your class here to see the domain on the search
        # if cls.__name__ == 'rule_engine':
        #     print domain
        try:
            return super(CoogSQL, cls).search(domain=domain, offset=offset,
                limit=limit, order=order, count=count, query=query)
        except:
            logging.getLogger('root').debug('Bad domain on model %s : %r' % (
                    cls.__name__, domain))
            raise

    def _get_creation_date(self, name):
        if not (hasattr(self, 'create_date') and self.create_date):
            return None
        return self.create_date

    @classmethod
    def copy(cls, objects, default=None):
        # This override is designed to automatically manage Unique constraints
        # on Char fields when duplicating. Ideally, those should be managed on
        # a per-model basis.
        constraints = []
        for constraint in cls._sql_constraints:
            if not isinstance(constraint[1], Unique):
                continue
            for column in constraint[1].columns:
                if column.name not in cls._fields:
                    continue
                field = cls._fields[column.name]
                if not isinstance(field, tryton_fields.Char):
                    continue
                constraints.append(column.name)
        if not constraints:
            return super(CoogSQL, cls).copy(objects, default=default)

        logging.getLogger('model').warning('Automatically changing %s when '
            'copying instances of %s' % (', '.join(constraints), cls.__name__))

        def single_copy(obj):
            new_defaults = default.copy() if default is not None else {}
            for constraint in constraints:
                value = new_defaults.get(constraint, getattr(obj, constraint))
                default[constraint] = None if value is None else 'temp_for_copy'
            copy = super(CoogSQL, cls).copy([obj], new_defaults)[0]
            for constraint in constraints:
                value = getattr(copy, constraint)
                if value is not None:
                    setattr(copy, constraint, '%s_%s' % (value, copy.id))
            copy.save()
            return copy

        return [single_copy(obj) for obj in objects]

    def get_icon(self, name=None):
        return None

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(CoogSQL, cls).search_global(text):
            yield record, rec_name, record.get_icon()

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def getter_void(self, name):
        pass

    def get_rec_name(self, name):
        return super(CoogSQL, self).get_rec_name(name)


class CoogView(ModelView, FunctionalErrorMixIn):
    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        if not Transaction().context.get('developper_read_view'):
            return super(CoogView, cls).fields_view_get(view_id, view_type)
        result = {
            'model': cls.__name__,
            'type': view_type,
            'field_childs': None,
            'view_id': 0,
            }
        xml = '<?xml version="1.0"?>'
        fnames = []
        if view_type == 'tree':
            xml += '<tree>'
            xml += '<field name="rec_name"/></tree>'
            fnames.append('rec_name')
        else:
            res = cls.fields_get()
            ignore_fields = cls._export_skips()
            xml += '<form col="2">'
            for fname in sorted(res):
                if fname in ignore_fields:
                    continue
                if res[fname]['type'] in ('one2many', 'many2many', 'text',
                        'dict'):
                    xml += '<field name="%s" colspan="2"/>' % fname
                else:
                    xml += '<label name="%s"/><field name="%s"/>' % (fname,
                        fname)
                fnames.append(fname)
            xml += '</form>'
        result['arch'] = xml
        result['fields'] = cls.fields_get(fnames)
        for fname in fnames:
            result['fields'][fname].update({
                    'string': result['fields'][fname]['string'] +
                    ' (%s)' % fname,
                    'states': {'readonly': True},
                    'on_change': [],
                    'on_change_with': [],
                    })
        return result

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def getter_void(self, name):
        pass


class ExpandTreeMixin(object):
    must_expand_tree = fields.Function(
        fields.Boolean('Must Expand Tree', states={'invisible': True}),
        '_expand_tree')

    def _expand_tree(self, name):
        return False


def expand_tree(name, test_field='must_expand_tree'):

    class ViewTreeState:
        __metaclass__ = PoolMeta
        __name__ = 'ir.ui.view_tree_state'

        @classmethod
        def get(cls, model, domain, child_name):
            result = super(ViewTreeState, cls).get(model, domain, child_name)
            if model == name and child_name:
                Model = Pool().get(name)
                domain = json.loads(domain)
                # don't generate tree if no domain define
                # performance issue
                if not domain:
                    return result
                roots = Model.search(domain)
                nodes = []
                selected = []

                def parse(records, path):
                    expanded = False
                    for record in records:
                        if getattr(record, test_field):
                            if path and not expanded:
                                nodes.append(path)
                                expanded = True
                            if not selected:
                                selected.append(path + (record.id,))
                        parse(getattr(record, child_name, []),
                            path + (record.id,))
                parse(roots, ())
                result = (json.dumps(nodes), json.dumps(selected))
            return result

    return ViewTreeState


class CoogWizard(Wizard):
    pass


class UnionMixin(TrytonUnionMixin):

    @classmethod
    def union_field(cls, name, Model):
        return Model._fields.get(name)

    @classmethod
    def union_column(cls, name, field, table, Model):
        column = Literal(None)
        union_field = cls.union_field(field.name, Model)
        if union_field:
            column = Column(table, union_field.name)
            if (isinstance(field, fields.Many2One)
                    and field.model_name == cls.__name__):
                target_model = union_field.model_name
                if target_model in cls.union_models():
                    column = cls.union_shard(column, target_model)
                else:
                    column = Literal(None)
        return column

    @classmethod
    def build_sub_query(cls, model, table, columns):
        return table.select(*columns)

    @classmethod
    def table_query(cls):
        queries = []
        for model in cls.union_models():
            table, columns = cls.union_columns(model)
            queries.append(cls.build_sub_query(model, table, columns))
        return Union(*queries)


class VoidStateAction(StateAction):
    def __init__(self):
        StateAction.__init__(self, None)

    def get_action(self):
        return None


class _RevisionMixin(object):
    _parent_name = None
    date = fields.Date('Date')

    @classmethod
    def __setup__(cls):
        super(_RevisionMixin, cls).__setup__()
        # TODO unique constraint on (parent, date) ?
        cls._order.insert(0, ('date', 'ASC'))

    @staticmethod
    def order_date(tables):
        table, _ = tables[None]
        return [Coalesce(table.date, datetime.date.min)]

    @classmethod
    def get_reverse_field_name(cls):
        return ''

    @staticmethod
    def revision_columns():
        return []

    @classmethod
    def get_values(cls, instances, names=None, date=None):
        'Return a dictionary with the variable name as key,'
        'and a dictionnary as value. The dictionnary value contains'
        'main instance id as key and variable value as value'

        transaction = Transaction()
        cursor = transaction.connection.cursor()
        table = cls.__table__()
        if names:
            columns_expected = list(set(cls.revision_columns()) & set(names))
        else:
            columns_expected = cls.revision_columns()

        parent_column = Column(table, cls._parent_name)
        target_field = cls.get_reverse_field_name()
        if target_field:
            to_add_in_values = [target_field]
            columns = [parent_column, table.id.as_(target_field)]
        else:
            to_add_in_values = ['id']
            columns = [parent_column, table.id]

        values = dict(((x, dict(((y.id, None) for y in instances)))
                for x in columns_expected + to_add_in_values))

        columns += [Column(table, c) for c in columns_expected]

        in_max = transaction.database.IN_MAX
        for i in range(0, len(instances), in_max):
            sub_ids = [c.id for c in instances[i:i + in_max]]
            where_parent = reduce_ids(parent_column, sub_ids)
            subquery = table.select(parent_column,
                Max(Coalesce(table.date, datetime.date.min)).as_('date'),
                where=((table.date <= date) | (table.date == Null))
                & where_parent,
                group_by=parent_column)
            cursor.execute(*table.join(subquery,
                    condition=(
                        parent_column == Column(subquery, cls._parent_name))
                    & (Coalesce(table.date, datetime.date.min) ==
                        Coalesce(subquery.date, datetime.date.min))
                    ).select(*columns))
            for elem in cursor_dict(cursor):
                for field_name, value in elem.iteritems():
                    if field_name == cls._parent_name:
                        continue
                    values[field_name][elem[cls._parent_name]] = value
        return values


class TaggedMixin(object):
    'Define a model with tags'

    tags = fields.Many2Many('tag-object', 'object_', 'tag', 'Tags')
    tags_name = fields.Function(
        fields.Char('Tags'),
        'on_change_with_tags_name', searcher='search_tags')

    @fields.depends('tags')
    def on_change_with_tags_name(self, name=None):
        return ', '.join([x.name for x in self.tags])

    @classmethod
    def search_tags(cls, name, clause):
        return [('tags.name',) + tuple(clause[1:])]


class MethodDefinition(CoogSQL, CoogView):
    'Method Definition'
    '''
        This model uses is what ir.model is for models and ir.model.field for
        fields. It allows to make references to python methods, so that
        configuration models can make reference to them.

        It shall typically be used for processes, endorsements, etc.

        Method signature should be:
            def my_method(self, caller=None, **kwargs)

        Methods will be called automatically, so regular args cannot be used.
    '''

    __name__ = 'ir.model.method'

    description = fields.Text('Description')
    method_name = fields.Selection('get_possible_methods', 'Method Name',
        required=True)
    model = fields.Many2One('ir.model', 'Model', required=True,
        ondelete='RESTRICT')
    name = fields.Char('Name')
    priority = fields.Integer('Priority', required=True)
    code_preview = fields.Function(
        fields.Text('Code Preview'),
        'on_change_with_code_preview')

    _get_method_cache = Cache('get_method')

    @classmethod
    def __setup__(cls):
        super(MethodDefinition, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.model, t.method_name),
                'The method name must be unique for a given model!'),
            ]
        cls._order = [('priority', 'ASC')]

    @classmethod
    def create(cls, vlist):
        created = super(MethodDefinition, cls).create(vlist)
        cls._get_method_cache.clear()
        return created

    @classmethod
    def delete(cls, ids):
        super(MethodDefinition, cls).delete(ids)
        cls._get_method_cache.clear()

    @classmethod
    def write(cls, *args):
        super(MethodDefinition, cls).write(*args)
        cls._get_method_cache.clear()

    @fields.depends('method_name', 'model')
    def on_change_with_code_preview(self, name=None):
        if not self.model or not self.method_name:
            return ''
        try:
            Model = Pool().get(self.model.model)
            func = getattr(Model, self.method_name)
            return ''.join(inspect.getsourcelines(func)[0])
        except:
            return 'Source Code unavailable'

    @fields.depends('model')
    def get_possible_methods(self):
        if not self.model:
            return []
        allowed_methods = []
        Model = Pool().get(self.model.model)
        for elem in dir(Model):
            # Filter attributes starting with '_'
            if elem.startswith('_'):
                continue
            attr = getattr(Model, elem)
            # Check it is a method !
            if not callable(attr):
                continue
            args = inspect.getargspec(attr)
            arg_names = args[0]
            # Check for instance method
            if not arg_names:
                continue
            if 'caller' not in arg_names:
                continue
            if arg_names[0] == 'self' and len(args[3]) != len(arg_names) - 1:
                continue
            if arg_names[0] == 'cls' and len(args[3]) != len(arg_names) - 2:
                continue
            if arg_names[0] not in ('self', 'cls'):
                continue
            allowed_methods.append((elem, elem))
        return allowed_methods

    @classmethod
    def get_method(cls, model_name, method_name):
        method_id = cls._get_method_cache.get((model_name, method_name),
            default=-1)
        if method_id != -1:
            return cls(method_id)
        instance = cls.search([('model.model', '=', model_name),
                ('method_name', '=', method_name)])[0]
        cls._get_method_cache.set((model_name, method_name), instance.id)
        return instance

    def execute(self, caller, callees, **kwargs):
        method = getattr(Pool().get(self.model.model), self.method_name)
        if not hasattr(method, 'im_self') or method.im_self:
            if not isinstance(callees, (list, tuple)):
                callees = [callees]
            return method(callees, caller=caller, **kwargs)
        else:
            if isinstance(callees, (list, tuple)):
                return [method(x, caller=caller, **kwargs) for x in callees]
            else:
                return method(callees, caller=caller, **kwargs)
