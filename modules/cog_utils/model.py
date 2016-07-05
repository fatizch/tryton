import inspect
import logging
import time
import datetime
import json

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
from trytond.rpc import RPC
from trytond.tools import reduce_ids, cursor_dict

import utils
import fields
import export
import summary

__all__ = [
    'error_manager',
    'FunctionalErrorMixIn',
    'CoopSQL',
    'CoopView',
    'CoopWizard',
    'VersionedObject',
    'VersionObject',
    'ObjectHistory',
    'expand_tree',
    'UnionMixin',
    'TaggedMixin',
    'MethodDefinition',
    ]


def serialize_this(data, from_field=None, set_rec_names=False):
    res = None
    if (isinstance(data, (tuple, list)) and data and
            isinstance(data[0], Model)):
        res = []
        for elem in data:
            res.append(serialize_this(elem))
    elif isinstance(data, Model):
        if isinstance(data, Model) and data.id > 0:
            res = data.id
            if isinstance(from_field, tryton_fields.Reference):
                res = '%s,%s' % (data.__name__, data.id)
        else:
            res = {}
            if data._values is not None:
                for key, value in data._values.iteritems():
                    res[key] = serialize_this(value, data._fields[key],
                        set_rec_names=set_rec_names)
                    if set_rec_names and isinstance(data._fields[key],
                            (tryton_fields.Many2One, tryton_fields.Reference)):
                        res[key + '.rec_name'] = getattr(value, 'rec_name', '')
    else:
        res = data
    return res


def dictionarize(instance, field_names):
    # Returns a dict which may be used to initialize a copy of instance with
    # for which the field_names fields are identical.
    # field_names is either a list of field names to extract (in that case,
    # O2Ms will be copied as ids, which may be bad), or a dict which states for
    # each model the field_names to extract
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
        elif isinstance(v, (list, tuple)):
            res[k] = [dictionarize(x, field_names) for x in v]
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


class CoopSQL(export.ExportImportMixin, ModelSQL, FunctionalErrorMixIn,
        summary.SummaryMixin):
    create_date_ = fields.Function(
        fields.DateTime('Creation date'),
        '_get_creation_date')

    @classmethod
    def __setup__(cls):
        super(CoopSQL, cls).__setup__()
        cls.__rpc__.update({'extract_object': RPC(instantiate=0)})

    @classmethod
    def __post_setup__(cls):
        super(CoopSQL, cls).__post_setup__()
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
        values = super(CoopSQL, self)._save_values
        for fname, fvalues in values.iteritems():
            field = self._fields[fname]
            if not isinstance(field, fields.One2Many):
                continue
            if not field._delete_missing:
                continue
            for idx, action in enumerate(fvalues):
                if action[0] == 'remove':
                    fvalues[idx] = ('delete', action[1])
        return values

    def __getattr__(self, name):
        cls = self.__class__
        field = cls._fields.get(name, None)
        if isinstance(field, fields.Function) and field.loader:
            return getattr(cls, field.loader)(self)
        return super(CoopSQL, self).__getattr__(name)

    def __setattr__(self, name, value):
        cls = self.__class__
        field = cls._fields.get(name, None)
        super(CoopSQL, self).__setattr__(name, value)
        if isinstance(field, fields.Function) and field.updater:
            getattr(cls, field.updater)(self, value)

    @classmethod
    def update_values_before_create(cls, vlist):
        pass

    @classmethod
    def create(cls, vlist):
        cls.update_values_before_create(vlist)
        return super(CoopSQL, cls).create(vlist)

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
        super(CoopSQL, cls).delete(instances)
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
            return super(CoopSQL, cls).search(domain=domain, offset=offset,
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
            return super(CoopSQL, cls).copy(objects, default=default)
        default = default.copy()

        for constraint in constraints:
            default[constraint] = 'temp_for_copy'
        logging.getLogger('model').warning('Automatically changing %s when '
            'copying instances of %s' % (', '.join(constraints), cls.__name__))

        def single_copy(obj):
            copy = super(CoopSQL, cls).copy([obj], default)[0]
            for constraint in constraints:
                setattr(copy, constraint, '%s_%s' % (
                    getattr(objects[0], constraint), copy.id))
            copy.save()
            return copy

        return [single_copy(obj) for obj in objects]

    def get_icon(self, name=None):
        return None

    @classmethod
    def search_global(cls, text):
        for record, rec_name, icon in super(CoopSQL, cls).search_global(text):
            yield record, rec_name, record.get_icon()

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def getter_void(self, name):
        pass

    def get_rec_name(self, name=None):
        return super(CoopSQL, self).get_rec_name(name)


class CoopView(ModelView, FunctionalErrorMixIn):
    @classmethod
    def fields_view_get(cls, view_id=None, view_type='form'):
        if not Transaction().context.get('developper_read_view'):
            return super(CoopView, cls).fields_view_get(view_id, view_type)
        result = {
            'model': cls.__name__,
            'type': view_type,
            'field_childs': None,
            'view_id': 0,
            }
        xml = '<?xml version="1.0"?>'
        fnames = []
        if view_type == 'tree':
            xml += '<tree string="%s">' % (cls.__doc__ or cls.__name__ +
                ' Dev View')
            xml += '<field name="rec_name"/></tree>'
            fnames.append('rec_name')
        else:
            res = cls.fields_get()
            ignore_fields = cls._export_skips()
            xml += '<form string="%s" col="2">' % (
                cls.__doc__ or cls.__name__ + ' Dev View')
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


class CoopWizard(Wizard):
    pass


class VersionedObject(CoopView):
    'Versionned Object'

    __name__ = 'utils.versionned_object'

    versions = fields.One2Many(None, 'main_elem', 'Versions',
        delete_missing=True)
    current_rec_name = fields.Function(
        fields.Char('Current Value'),
        'get_current_rec_name')

    @classmethod
    def version_model(cls):
        return 'utils.version_object'

    @classmethod
    def __setup__(cls):
        super(VersionedObject, cls).__setup__()
        cls.versions.model_name = cls.version_model()

    def get_previous_version(self, at_date):
        prev_version = None
        for version in self.versions:
            if version.start_date > at_date:
                return prev_version
            prev_version = version
        return prev_version

    def append_version(self, version):
        rank = 0
        prev_version = self.get_previous_version(version.start_date)
        if prev_version:
            prev_version.end_date = version.start_date - 1
            rank = self.versions.index(prev_version) + 1
        self.versions.insert(rank, version)
        return self

    def get_version_at_date(self, date):
        return utils.get_good_version_at_date(self, 'versions', date)

    def get_current_rec_name(self, name):
        vers = self.get_version_at_date(utils.today())
        if vers:
            return vers.rec_name
        return ''

    @classmethod
    def default_versions(cls):
        return [{'start_date': Transaction().context.get('start_date',
                    Pool().get('ir.date').today())}]


class VersionObject(CoopView):
    'Version Object'

    __name__ = 'utils.version_object'

    main_elem = fields.Many2One(None, 'Descriptor', ondelete='CASCADE',
        required=True, select=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')

    @classmethod
    def main_model(cls):
        return 'utils.versionned_object'

    @classmethod
    def __setup__(cls):
        super(VersionObject, cls).__setup__()
        cls.main_elem.model_name = cls.main_model()

    @staticmethod
    def default_start_date():
        return Transaction().context.get('start_date', utils.today())


class ObjectHistory(CoopSQL, CoopView):
    'Object History'

    __name__ = 'coop.object.history'

    date = fields.DateTime('Change Date')
    from_object = fields.Many2One(None, 'From Object')
    user = fields.Many2One('res.user', 'User')

    @classmethod
    def __setup__(cls):
        cls.from_object.model_name = cls.get_object_model()
        object_name = cls.get_object_name()
        if object_name:
            cls.from_object.string = object_name
        super(ObjectHistory, cls).__setup__()
        cls._order.insert(0, ('date', 'DESC'))

    @classmethod
    def get_object_model(cls):
        raise NotImplementedError

    @classmethod
    def get_object_name(cls):
        return 'From Object'

    @classmethod
    def _table_query_fields(cls):
        Object = Pool().get(cls.get_object_model())
        table = '%s__history' % Object._table
        return [
            'MIN("%s".__id) AS id' % table,
            '"%s".id AS from_object' % table,
            ('MIN(COALESCE("%s".write_date, "%s".create_date)) AS date'
                % (table, table)),
            ('COALESCE("%s".write_uid, "%s".create_uid) AS user'
                % (table, table)),
        ] + [
            '"%s"."%s"' % (table, name)
            for name, field in cls._fields.iteritems()
            if name not in ('id', 'from_object', 'date', 'user')
            and not hasattr(field, 'set')]

    @classmethod
    def _table_query_group(cls):
        Object = Pool().get(cls.get_object_model())
        table = '%s__history' % Object._table
        return [
            '"%s".id' % table,
            'COALESCE("%s".write_uid, "%s".create_uid)' % (table, table),
            ] + [
            '"%s"."%s"' % (table, name)
            for name, field in cls._fields.iteritems()
            if (name not in ('id', 'from_object', 'date', 'user')
                and not hasattr(field, 'set'))]

    @classmethod
    def table_query(cls):
        Object = Pool().get(cls.get_object_model())
        return ((
            'SELECT ' + (', '.join(cls._table_query_fields()))
            + ' FROM "%s__history" GROUP BY '
            + (', '.join(cls._table_query_group()))) % Object._table, [])

    @classmethod
    def read(cls, ids, fields_names=None):
        res = super(ObjectHistory, cls).read(ids, fields_names=fields_names)

        # Remove microsecond from timestamp
        for values in res:
            if 'date' in values:
                if isinstance(values['date'], basestring):
                    values['date'] = datetime.datetime(
                        *time.strptime(
                            values['date'], '%Y-%m-%d %H:%M:%S.%f')[:6])
                values['date'] = values['date'].replace(microsecond=0)
        return res


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
                where=((table.date <= date) | (table.date == None))
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


class MethodDefinition(CoopSQL, CoopView):
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
