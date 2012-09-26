import copy

from trytond.pyson import Eval, Bool
from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.wizard import Wizard
from trytond.pool import Pool

import utils


class CoopSQL(ModelSQL):
    'Root class for all stored classes'

    is_used = fields.Function(fields.Boolean('Is Used'), 'get_is_used')

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
        key_dict = dict((getattr(instance, key_name), instance.id)
            for instance in instances)
        for cur_class, var_name in cls.get_class_where_used():
            Class = Pool().get(cur_class)
            for found_instance in Class.search(
                [
                    (var_name, 'in',
                        [getattr(instance, key_name) for instance in instances]
                    )
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
        res = dict((instance.id,
                len(using_inst[instance.id]) > 0) for instance in instances)
        return res

    @classmethod
    def can_be_deleted(cls, instances):
        using_inst = cls.get_instances_using_me(instances)
        res = {}
        for instance in instances:
            if len(using_inst[instance.id]) == 0:
                res[instance.id] = (True, '', [])
            for using_instance in using_inst[instance.id]:
                res[instance.id] = (False, 'item_used',
                    (
                        instance.rec_name,
                        using_instance.rec_name,
                        utils.translate_model_name(using_instance.__class__),
                        using_instance.id,
                        ))
                continue
        return res

    @classmethod
    def delete(cls, instances):
        can_be_del_dict = cls.can_be_deleted(instances)
        for instance in instances:
            (can_be_deleted, error, error_args) = can_be_del_dict[instance.id]
            if not can_be_deleted:
                cls.raise_user_error(error, error_args)

        super(CoopSQL, cls).delete(instances)


class CoopView(ModelView):
    pass


class CoopWizard(Wizard):
    pass


class TableOfTable(CoopSQL, CoopView):
    'Table of table'

    __name__ = 'coop.table_of_table'
    #unnecessary line, but to think for children class to replace '.' by '_'
    _table = 'coop_table_of_table'

    my_model_name = fields.Char('Model Name')
    key = fields.Char('Key', states={'readonly': Bool(Eval('is_used'))},
        depends=['is_used'])
    name = fields.Char('Value', required=True, translate=True)
    parent = fields.Many2One(None, 'Parent',
        ondelete='CASCADE')
    childs = fields.One2Many('coop.table_of_table', 'parent', 'Sub values',
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
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        domain.append(('my_model_name', '=', cls.__name__))
        return super(TableOfTable, cls).search(domain, offset=offset,
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
    versions = fields.One2Many(
        None,
        'main_elem',
        'Versionned Rates')

    @classmethod
    def version_model(cls):
        raise NotImplementedError

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


class VersionObject(CoopView):
    main_elem = fields.Many2One(
        None,
        'Descriptor',
        ondelete='CASCADE')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')

    @classmethod
    def main_model(cls):
        raise NotImplementedError

    @classmethod
    def __setup__(cls):
        super(VersionObject, cls).__setup__()
        main_elem = copy.copy(getattr(cls, 'main_elem'))
        main_elem.model_name = cls.main_model()
        setattr(cls, 'main_elem', main_elem)
