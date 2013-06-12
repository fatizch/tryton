import copy
import time
import datetime
import json

from trytond.pyson import Eval, Bool
from trytond.model import ModelView, ModelSQL, fields as tryton_fields
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.wizard import Wizard

import utils
import coop_string
import fields
import export


__all__ = [
    'CoopSQL',
    'CoopView',
    'CoopWizard',
    'TableOfTable',
    'DynamicSelection',
    'VersionedObject',
    'VersionObject',
    'ObjectHistory',
    'expand_tree',
]


class CoopSQL(export.ExportImportMixin, ModelSQL):
    'Root class for all stored classes'

    is_used = fields.Function(
        fields.Boolean('Is Used'), 'get_is_used')

    @classmethod
    def __setup__(cls):
        super(CoopSQL, cls).__setup__()
        cls._error_messages.update({
            'item_used': 'This item (%s) is used by %s (%s, %s)',
        })

    @staticmethod
    def get_class_where_used():
        '''Method to override in all sub class and return the list of tuple
        class, var_name of object using this class. Needed when you can't
        guess dependency with foreign keys'''
        return []

    @classmethod
    def get_instances_using_me(cls, instances):
        res = dict((instance.id, []) for instance in instances)
        key_name = cls.get_func_pk_name()
        if not key_name:
            return res
        key_dict = dict(
            (getattr(instance, key_name), instance.id)
            for instance in instances)
        for cur_class, var_name in cls.get_class_where_used():
            Class = Pool().get(cur_class)
            for found_instance in Class.search(
                    [
                        (var_name, 'in',
                            [getattr(cur_inst, key_name)
                                for cur_inst in instances])
                    ]):
                cur_id = key_dict[getattr(found_instance, var_name)]
                res[cur_id].append(found_instance)
        return res

    @staticmethod
    def get_func_pk_name():
        'return the functional key var name used when not using the id'

    @classmethod
    def get_is_used(cls, instances, name):
        using_inst = cls.get_instances_using_me(instances)
        res = dict(
            (instance.id, len(using_inst[instance.id]) > 0)
            for instance in instances)
        return res

    @classmethod
    def can_be_deleted(cls, instances):
        using_inst = cls.get_instances_using_me(instances)
        for instance in instances:
            for using_instance in using_inst[instance.id]:
                cls.raise_user_error(
                    'item_used',
                    (
                        instance.rec_name,
                        using_instance.rec_name,
                        coop_string.translate_model_name(
                            using_instance.__class__),
                        using_instance.id,
                    ))

    @classmethod
    def delete(cls, instances):
        # Do not remove, needed to avoid infinite recursion in case a model
        # has a O2Ref which can lead to itself.
        if not instances:
            return

        cls.can_be_deleted(instances)

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
    def search_rec_name(cls, name, clause):
        if (hasattr(cls, 'code')
                and cls.search([('code',) + clause[1:]], limit=1)):
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]

    @classmethod
    def search(
            cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        #Set your class here to see the domain on the search
        # if cls.__name__ == 'ins_contract.loan_share':
        #     print domain
        return super(CoopSQL, cls).search(
            domain=domain, offset=offset,
            limit=limit, order=order, count=count, query_string=query_string)

    def get_currency(self):
        print self.__name__
        raise NotImplementedError

    def get_currency_id(self, name):
        return self.get_currency().id

    def get_currency_digits(self, name):
        return (self.currency.digits
            if not utils.is_none(self, 'currency') else 2)

    def get_currency_symbol(self, name):
        return (self.currency.symbol
            if not utils.is_none(self, 'currency') else '')

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
            #Code must be unique and action "copy" stores in db during process
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


class CoopView(ModelView):
    must_expand_tree = fields.Function(fields.Boolean('Must Expand Tree'),
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


class TableOfTable(CoopSQL, CoopView):
    'Table of table'

    __name__ = 'coop.table_of_table'
    #unnecessary line, but to think for children class to replace '.' by '_'
    _table = 'coop_table_of_table'

    my_model_name = fields.Char('Model Name')
    key = fields.Char(
        'Key', states={'readonly': Bool(Eval('is_used'))}, depends=['is_used'])
    name = fields.Char('Value', required=True, translate=True)
    parent = fields.Many2One(
        None, 'Parent', ondelete='CASCADE')
    childs = fields.One2Many(
        'coop.table_of_table', 'parent', 'Sub values',
        domain=[('my_model_name', '=', Eval('my_model_name'))],
        depends=['my_model_name', 'parent'],
        states={'invisible': Bool(Eval('parent'))},)

    @classmethod
    def __setup__(cls):
        super(TableOfTable, cls).__setup__()
        cls.childs = copy.copy(cls.childs)
        cls.childs.model_name = cls.__name__
        cls.parent = copy.copy(cls.parent)
        cls.parent.model_name = cls.childs.model_name

    @classmethod
    def default_my_model_name(cls):
        return cls.__name__

    @classmethod
    def search(
            cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        domain.append(('my_model_name', '=', cls.__name__))
        return super(TableOfTable, cls).search(
            domain, offset=offset,
            limit=limit, order=order, count=count, query_string=query_string)

    @staticmethod
    def get_values_as_selection(model_name):
        res = []
        DynamicSelection = Pool().get(model_name)
        for dyn_sel in DynamicSelection.search([]):
            res.append((dyn_sel.key, dyn_sel.name))
        return res

    @staticmethod
    def get_class_where_used():
        raise NotImplementedError

    @staticmethod
    def get_func_pk_name():
        return 'key'


class DynamicSelection(TableOfTable):
    'Dynamic Selection'

    __name__ = 'coop.dyn_selection'
    _table = 'coop_table_of_table'


class VersionedObject(CoopView):
    'Versionned Object'

    __name__ = 'utils.versionned_object'

    versions = fields.One2Many(
        None,
        'main_elem',
        'Versions')
    current_rec_name = fields.Function(
        fields.Char('Current Value'),
        'get_current_rec_name')

    @classmethod
    def version_model(cls):
        return 'utils.version_object'

    @classmethod
    def __setup__(cls):
        super(VersionedObject, cls).__setup__()
        versions = copy.copy(getattr(cls, 'versions'))
        versions.model_name = cls.version_model()
        setattr(cls, 'versions', versions)

    # To do : CTD0069
    # Check there is no overlapping of versions before save

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
        main_elem = copy.copy(getattr(cls, 'main_elem'))
        main_elem.model_name = cls.main_model()
        setattr(cls, 'main_elem', main_elem)

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
        cls.from_object = copy.copy(cls.from_object)
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
