import logging
import time
import datetime
import json

from sql.aggregate import Max
from sql.conditionals import Coalesce
from sql import Union, Column, Literal

from trytond.model import Model, ModelView, ModelSQL, fields as tryton_fields
from trytond.model import UnionMixin as TrytonUnionMixin
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateAction
from trytond.rpc import RPC
from trytond.tools import reduce_ids

import utils
import fields
import export


__all__ = [
    'CoopSQL',
    'CoopView',
    'CoopWizard',
    'VersionedObject',
    'VersionObject',
    'ObjectHistory',
    'expand_tree',
    'UnionMixin',
    'TaggedMixin',
    ]


def serialize_this(the_data, from_field=None):
    res = None
    if (isinstance(the_data, list) and the_data != [] and
            isinstance(the_data[0], Model)):
        res = []
        for elem in the_data:
            res.append(serialize_this(elem))
    elif isinstance(the_data, Model):
        if isinstance(the_data, Model) and the_data.id > 0:
            res = the_data.id
            if isinstance(from_field, tryton_fields.Reference):
                res = '%s,%s' % (the_data.__name__, the_data.id)
        else:
            res = {}
            if not the_data._values is None:
                for key, value in the_data._values.iteritems():
                    res[key] = serialize_this(value, the_data._fields[key])
    else:
        res = the_data
    return res


class CoopSQL(export.ExportImportMixin, ModelSQL):
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
        for field_name, field in cls._fields.iteritems():
            if not isinstance(field, fields.Many2One):
                continue
            if getattr(field, '_on_delete_not_set', None):
                logging.getLogger('modules').warning('Ondelete not set for '
                    'field %s on model %s' % (field_name, cls.__name__))

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
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query=False):
        #Set your class here to see the domain on the search
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
        constraints = []
        for constraint in cls._sql_constraints:
            if 'UNIQUE' in constraint[1]:
                constraints.append(constraint[1][7:-1])
        if len(constraints) == 1:
            if default is None:
                default = {}
            default = default.copy()
            default[constraints[0]] = 'temp_for_copy'

            res = super(CoopSQL, cls).copy(objects, default=default)
            for clone, original in zip(res, objects):
                i = 1
                while cls.search([
                        (constraints[0], '=', '%s_%s' % (
                            getattr(original, constraints[0]), i))]):
                    i += 1
                setattr(clone, constraints[0], '%s_%s' % (
                    getattr(original, constraints[0]), i))
                clone.save()
            return res
        else:
            return super(CoopSQL, cls).copy(objects, default=default)

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def getter_void(self, name):
        pass

    def get_rec_name(self, name=None):
        return super(CoopSQL, self).get_rec_name(name)

    @classmethod
    def get_var_names_for_full_extract(cls):
        'returns a list of varname or tuple varname extract_kind (full, light)'
        return ['code', 'name']

    @classmethod
    def get_var_names_for_light_extract(cls):
        'returns a list of varname or tuple varname extract_kind (full, light)'
        return ['code']

    def extract_object(self, extract_kind='full'):
        if extract_kind == 'full':
            var_names = self.get_var_names_for_full_extract()
        elif extract_kind == 'light':
            var_names = self.get_var_names_for_light_extract()
        return utils.extract_object(self, var_names)


class CoopView(ModelView):
    must_expand_tree = fields.Function(
        fields.Boolean('Must Expand Tree', states={'invisible': True}),
        '_expand_tree')

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def getter_void(self, name):
        pass

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

    versions = fields.One2Many(None, 'main_elem', 'Versions')
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

    main_elem = fields.Many2One(None, 'Descriptor', ondelete='CASCADE')
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

        cursor = Transaction().cursor
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

        in_max = cursor.IN_MAX
        for i in range(0, len(instances), in_max):
            sub_ids = [c.id for c in instances[i:i + in_max]]
            where_parent = reduce_ids(parent_column, sub_ids)
            subquery = table.select(parent_column,
                Max(Coalesce(table.date, datetime.date.min)).as_('date'),
                where=((table.date <= date) | (table.date == None))
                & where_parent,
                group_by=parent_column)
            cursor.execute(*table.join(subquery,
                    condition=
                    (parent_column == Column(subquery, cls._parent_name))
                    & (Coalesce(table.date, datetime.date.min) ==
                        Coalesce(subquery.date, datetime.date.min))
                    ).select(*columns))
            for elem in cursor.dictfetchall():
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
