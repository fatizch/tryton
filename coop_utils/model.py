import copy
import time
import datetime
try:
    import simplejson as json
except ImportError:
    import json

from trytond.pyson import Eval, Bool
from trytond.model import Model, ModelView, ModelSQL, fields as tryton_fields
from trytond.wizard import Wizard
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.rpc import RPC
from trytond.protocols.jsonrpc import JSONEncoder, object_hook
from trytond.exceptions import UserError

import utils
import coop_string
import fields


__all__ = [
    'NotExportImport',
    'ExportImportMixin',
    'CoopSQL',
    'CoopView',
    'CoopWizard',
    'TableOfTable',
    'DynamicSelection',
    'VersionedObject',
    'VersionObject',
    'ObjectHistory',
    'Group',
]


class NotExportImport(Exception):
    pass


class ExportImportMixin(Model):
    'Mixin to support export/import in json'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(ExportImportMixin, cls).__setup__()
        cls.__rpc__['export_json'] = RPC(instantiate=0,
            result=lambda r: json.dumps(r, cls=JSONEncoder))
        cls.__rpc__['import_json'] = RPC(readonly=False,
            result=lambda r: None)

    def _prepare_for_import(self):
        pass

    def _post_import(self):
        pass

    @classmethod
    def _export_keys(cls):
        # TODO : Look for a field with 'UNIQUE' and 'required' attributes set
        if 'code' in cls._fields:
            return set(['code'])
        elif 'name' in cls._fields:
            return set(['name'])
        else:
            return set()

    @classmethod
    def _export_skips(cls):
        return set((
            'id', 'create_uid', 'write_uid', 'create_date', 'write_date'))

    @classmethod
    def _export_light(cls):
        return set()

    @classmethod
    def _export_force_recreate(cls):
        force = set()
        for field_name, field in cls._fields.iteritems():
            if isinstance(field, tryton_fields.One2Many):
                force.add(field_name)
        return force

    def _export_get_key(self):
        class_keys = self._export_keys()
        if not class_keys:
            raise NotExportImport('No keys defined for %s' % self.__name__)
        result = []
        for k in class_keys:
            keys = k.split('.')
            value = self
            for idx in range(0, len(keys)):
                value = getattr(value, keys[idx])
            result.append((k, value))
        return tuple(result)

    @classmethod
    def _export_find_instance(cls, instance_key):
        if not instance_key:
            return None
        try:
            domain = [(key, '=', value) for key, value in instance_key]
        except ValueError:
            return None
        result = cls.search(domain)
        if not result:
            return None
        if len(result) > 1:
            raise NotExportImport(
                'Multiple result found for key %s in class %s' % (
                    instance_key, cls.__name__))
        return result[0]

    def export_json(self, exported=None, from_field=None, force_key=None):
        if exported is None:
            exported = {}
        if self.__name__ not in exported:
            exported[self.__name__] = set()
        if force_key is None:
            my_key = self._export_get_key()
        else:
            if len(force_key) == 3 and isinstance(force_key[2], int):
                my_key = force_key
            else:
                my_key = force_key[1]
        exported[self.__name__].add(my_key)
        values = {
            '__name__': self.__name__,
            '_export_key': my_key}
        field_order = []
        for field_name, field in self._fields.iteritems():
            if field_name in self._export_skips():
                continue
            if isinstance(field, tryton_fields.Function) and not isinstance(
                    field, tryton_fields.Property):
                continue
            field_value = getattr(self, field_name)
            if field_value is None:
                continue
            field_order.append(field_name)
            if hasattr(self, '_export_override_%s' % field_name):
                values[field_name] = getattr(
                    self, '_export_override_%s' % field_name)(exported, my_key)
                continue
            if isinstance(field, (
                    tryton_fields.Many2One, tryton_fields.One2One)):
                if not hasattr(field_value, 'export_json'):
                    raise NotExportImport(
                        '%s - %s' % (self.__name__, field_value.__name__))
                if field_name == from_field and force_key:
                    values[field_name] = force_key[0]
                    continue
                field_key = field_value._export_get_key()
                if field_key in exported.get(field_value.__name__, {}) or \
                        field_name in self._export_light():
                    values[field_name] = field_key
                else:
                    values[field_name] = field_value.export_json(exported)
            elif isinstance(field, tryton_fields.Reference):
                if not hasattr(field_value, 'export_json'):
                    raise NotExportImport(
                        '%s - %s' % (self.__name__, field_value.__name__))
                if field_name == from_field and force_key:
                    values[field_name] = (field_value.__name__, force_key[0])
                    continue
                field_key = field_value._export_get_key()
                if field_key in exported.get(field_value.__name__, {}) or \
                        field_name in self._export_light():
                    values[field_name] = (field_value.__name__, field_key)
                else:
                    values[field_name] = field_value.export_json(exported)
            elif isinstance(field, tryton_fields.One2Many) and field.size != 1:
                if not hasattr(Pool().get(field.model_name), 'export_json'):
                    raise NotExportImport(
                        '%s - %s' % (self.__name__, field.model_name))
                field_export_value = []
                idx = 1
                for elem in field_value:
                    if field_name in self._export_force_recreate():
                        try:
                            elem_key = (my_key, elem._export_get_key())
                        except NotExportImport:
                            elem_key = (my_key, field_name, idx)
                        field_export_value.append(elem.export_json(
                            exported, field.field, elem_key))
                    else:
                        field_export_value.append(elem.export_json(
                            exported))
                    idx += 1
                values[field_name] = field_export_value
            elif isinstance(field, tryton_fields.One2Many) and field.size == 1:
                if len(field_value) != 1:
                    continue
                field_value = field_value[0]
                if not hasattr(field_value, 'export_json'):
                    raise NotExportImport(
                        '%s - %s' % (self.__name__, field_value.__name__))
                field_key = field_value._export_get_key()
                if field_key in exported.get(field_value.__name__, {}) or \
                        field_name in self._export_light():
                    values[field_name] = field_key
                else:
                    values[field_name] = field_value.export_json(exported)
            elif isinstance(field, tryton_fields.Many2Many):
                target_field = Pool().get(
                    field.relation_name)._fields[field.target]
                if not hasattr(
                        Pool().get(target_field.model_name), 'export_json'):
                    raise NotExportImport(
                        '%s - %s' % (self.__name__, target_field.model_name))
                field_export_value = []
                for elem in field_value:
                    elem_key = elem._export_get_key()
                    if elem_key in exported.get(elem.__name__, {}) or \
                            field_name in self._export_light():
                        field_export_value.append(elem_key)
                    else:
                        field_export_value.append(elem.export_json(exported))
                values[field_name] = field_export_value
            else:
                values[field_name] = getattr(self, field_name)
        values['_export_order'] = field_order
        return values

    @classmethod
    def _import_json(
            cls, values, force_recreate=False, created=None, relink=None,
            root=True, cur_path=None):
        # Useful for debugging
        # print cur_path
        assert values['__name__'] == cls.__name__
        save = True
        if created is None:
            created = {}
        if relink is None:
            relink = []
        if cur_path is None:
            cur_path = [cls.__name__]
        to_relink = []
        my_key = values['_export_key']
        good_instance = cls._export_find_instance(my_key)
        if good_instance is None:
            good_instance = cls()
        else:
            good_instance._prepare_for_import()
        for field_name in values['_export_order']:
            if not field_name in values:
                continue
            cur_path.append(field_name)
            field = cls._fields[field_name]
            field_value = values[field_name]
            if isinstance(field, (
                    tryton_fields.Many2One, tryton_fields.One2One)):
                TargetModel = Pool().get(field.model_name)
                if isinstance(field_value, tuple):
                    if (TargetModel.__name__ in created and
                            field_value in created[TargetModel.__name__]):
                        target_value = created[
                            TargetModel.__name__][field_value]
                        if hasattr(target_value, 'id') and target_value.id:
                            setattr(good_instance, field_name, created[
                                TargetModel.__name__][field_value])
                        else:
                            to_relink.append(
                                (field_name, (field.model_name, field_value)))
                            save = False
                    else:
                        good_value = TargetModel._export_find_instance(
                            field_value)
                        if good_value:
                            setattr(good_instance, field_name, good_value.id)
                        else:
                            to_relink.append(
                                (field_name, (field.model_name, field_value)))
                            save = False
                else:
                    setattr(
                        good_instance, field_name, TargetModel._import_json(
                            field_value, created=created, relink=relink,
                            root=False, cur_path=cur_path))
            elif isinstance(field, tryton_fields.Reference):
                if isinstance(field_value, tuple):
                    field_model, field_value = field_value
                    TargetModel = Pool().get(field_model)
                    if (TargetModel.__name__ in created and
                            field_value in created[TargetModel.__name__]):
                        target_value = created[
                            TargetModel.__name__][field_value]
                        if hasattr(target_value, 'id') and target_value.id:
                            setattr(good_instance, field_name, created[
                                TargetModel.__name__][field_value])
                        else:
                            to_relink.append(
                                (field_name, (field.model_name, field_value)))
                            save = False
                    else:
                        good_value = TargetModel._export_find_instance(
                            field_value)
                        if good_value:
                            setattr(good_instance, field_name, good_value)
                        else:
                            to_relink.append(
                                (field_name, (field_model, field_value)))
                            save = False
                else:
                    TargetModel = Pool().get(field_value.__name__)
                    setattr(
                        good_instance, field_name, TargetModel._import_json(
                            field_value, created=created, relink=relink,
                            root=False, cur_path=cur_path))
            elif isinstance(field, tryton_fields.One2Many) and field.size != 1:
                existing_values = getattr(good_instance, field_name) \
                    if hasattr(good_instance, field_name) else None
                TargetModel = Pool().get(field.model_name)
                if field_name in cls._export_force_recreate() and \
                        existing_values:
                    TargetModel.delete([elem for elem in existing_values])
                good_value = []
                for elem in field_value:
                    good_value.append(TargetModel._import_json(
                        elem, created=created, relink=relink,
                        root=False, cur_path=cur_path))
            elif isinstance(field, tryton_fields.One2Many) and field.size == 1:
                TargetModel = Pool().get(field.model_name)
                if isinstance(field_value, tuple):
                    if (TargetModel.__name__ in created and
                            field_value in created[TargetModel.__name__]):
                        setattr(good_instance, field_name, [created[
                            TargetModel.__name__][field_value]])
                    else:
                        good_value = TargetModel._export_find_instance(
                            field_value)
                        if good_value:
                            setattr(
                                good_instance, field_name, [good_value.id])
                        else:
                            to_relink.append((
                                field_name, (field.model_name, [field_value])))
                else:
                    setattr(
                        good_instance, field_name, [
                            TargetModel._import_json(
                                field_value, created=created, relink=relink,
                                root=False, cur_path=cur_path)])
            elif isinstance(field, tryton_fields.Many2Many):
                if (hasattr(good_instance, 'id') and good_instance.id):
                    # For now, just recreate the links
                    RelationModel = Pool().get(field.relation_name)
                    RelationModel.delete(RelationModel.search([
                        (field.origin, '=', good_instance.id)]))
                TargetModel = Pool().get(Pool().get(
                    field.relation_name)._fields[field.target].model_name)
                relinks = []
                good_values = []
                for elem in field_value:
                    if isinstance(elem, tuple):
                        if (TargetModel.__name__ in created and
                                elem in created[TargetModel.__name__]):
                            good_values.append(
                                created[TargetModel.__name__][elem])
                        else:
                            good_value = TargetModel._export_find_instance(
                                elem)
                            if good_value:
                                good_values.append(good_value)
                            else:
                                relinks.append(elem)
                    else:
                        good_values.append(TargetModel._import_json(
                            elem, created=created, relink=relink,
                            root=False, cur_path=cur_path))
                setattr(good_instance, field_name, good_values)
                if relinks:
                    to_relink.append(
                        (field_name, (TargetModel.__name__, relinks)))
            else:
                setattr(good_instance, field_name, field_value)
            cur_path.pop(-1)
        if save:
            try:
                good_instance.save()
            except:
                # Useful for debugging
                # print '\n'.join([str(x) for x in relink])
                # print utils.format_data(created)
                # print utils.format_data(good_instance)
                raise
            good_instance._post_import()
        if not cls.__name__ in created:
            created[cls.__name__] = {}
        if my_key in created[cls.__name__]:
            raise NotExportImport('Already existing key (%s) for class %s' % (
                my_key, cls.__name__))
        created[cls.__name__].update({my_key: good_instance})
        if to_relink:
            relink.append(((cls.__name__, my_key), dict([
                (name, value) for name, value in to_relink])))
        if not root:
            return good_instance
        # Useful for debugging
        # print utils.format_data(created)
        # print '\n'.join([str(x) for x in relink])
        while len(relink) > 0:
            cur_errs = []
            to_del = []
            idx = 0
            for key, value in relink:
                # print utils.format_data({key: value})
                working_instance = created[key[0]][key[1]]
                for field_name, field_value in value.iteritems():
                    if isinstance(field_value[1], list):
                        existing = list(getattr(
                            working_instance, field_name))
                        for elem in field_value[1]:
                            existing.append(created[field_value[0]][elem])
                        setattr(working_instance, field_name, existing)
                    else:
                        value = created[field_value[0]][field_value[1]]
                        if not (hasattr(value, 'id') and value.id):
                            continue
                        setattr(working_instance, field_name, value)
                try:
                    working_instance.save()
                except UserError, e:
                    cur_errs.append(e.args)
                    continue
                    # raise
                working_instance._post_import()
                to_del.append(idx)
                idx += 1
            for k in sorted(to_del, reverse=True):
                relink.pop(k)
            if len(to_del) == 0:
                print '#' * 80
                print 'CREATED DATA'
                print utils.format_data(created)
                print '#' * 80
                print 'RELINKS'
                print '\n'.join([str(x) for x in relink])
                print '#' * 80
                print 'User Errors'
                print '\n'.join((utils.format_data(err) for err in cur_errs))
                raise NotExportImport('Infinite loop detected in import')
        return good_instance

    @classmethod
    def import_json(cls, values):
        with Transaction().set_user(0):
            with Transaction().set_context(__importing__=True):
                if isinstance(values, basestring):
                    values = json.loads(values, object_hook=object_hook)
                    values = utils.recursive_list_tuple_convert(values)
                record = cls._import_json(values)
        return record


class CoopSQL(ExportImportMixin, ModelSQL):
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
        key_dict = dict((getattr(instance, key_name), instance.id)
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
                        coop_string.translate_model_name(
                            using_instance.__class__),
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

    @classmethod
    def search_rec_name(cls, name, clause):
        if (hasattr(cls, 'code')
                and cls.search([('code',) + clause[1:]], limit=1)):
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]

    @classmethod
    def search(cls, domain, offset=0, limit=None, order=None, count=False,
            query_string=False):
        #Set your class here to see the domain on the search
        # if cls.__name__ == 'ins_contract.option':
        #     print domain
        return super(CoopSQL, cls).search(domain=domain, offset=offset,
            limit=limit, order=order, count=count, query_string=query_string)

    def get_currency(self):
        print self.__name__
        raise NotImplementedError

    @classmethod
    def clean_object_before_copy(cls, default):
        pass

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
            cls.clean_object_before_copy(default)
            #Code must be unique and action "copy" stores in db during process
            default[constraints[0]] = 'temp_for_copy'
            res = super(CoopSQL, cls).copy(objects, default=default)
            for clone, original in zip(res, objects):
                i = 1
                while cls.search([
                        (constraints[0], '=', '%s_%s' % (
                            getattr(original, constraints[0]), i))]):
                    i += 1
                setattr(clone, constraints[0],
                    '%s_%s' % (getattr(original, constraints[0]), i))
                clone.save()
            return res
        else:
            res = super(CoopSQL, cls).copy(objects, default=default)

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def getter_void(self, name):
        pass

    def get_rec_name(self, name=None):
        return super(CoopSQL, self).get_rec_name(name)


class CoopView(ModelView):
    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    def getter_void(self, name):
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
        ] + ['"%s"."%s"' % (table, name)
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
        ] + ['"%s"."%s"' % (table, name)
            for name, field in cls._fields.iteritems()
            if (name not in ('id', 'from_object', 'date', 'user')
                and not hasattr(field, 'set'))]

    @classmethod
    def table_query(cls):
        Object = Pool().get(cls.get_object_model())
        return (('SELECT ' + (', '.join(cls._table_query_fields()))
                + ' FROM "%s__history" GROUP BY '
                + (', '.join(cls._table_query_group())))
            % Object._table, [])

    @classmethod
    def read(cls, ids, fields_names=None):
        res = super(ObjectHistory, cls).read(ids,
            fields_names=fields_names)

        # Remove microsecond from timestamp
        for values in res:
            if 'date' in values:
                if isinstance(values['date'], basestring):
                    values['date'] = datetime.datetime(
                        *time.strptime(values['date'],
                            '%Y-%m-%d %H:%M:%S.%f')[:6])
                values['date'] = values['date'].replace(microsecond=0)
        return res


class Group(ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'res.group'

    @classmethod
    def _export_skips(cls):
        result = super(Group, cls)._export_skips()
        result.add('users')
        return result

    @classmethod
    def _export_keys(cls):
        return set(['name'])


def add_export_to_model(models):
    def class_generator(model_name, keys):
        class GenericClass(ExportImportMixin):
            __metaclass__ = PoolMeta
            __name__ = model_name

            @classmethod
            def _export_keys(cls):
                return set(keys)

        return GenericClass

    classes = []
    for model, keys in models:
        classes.append(class_generator(model, keys))
    Pool.register(*classes, module='coop_utils', type_='model')


add_export_to_model([
    ('ir.model', ('model',)),
    ('ir.model.field', ('name', 'model.model')),
    ('res.group', ('name',)),
    ('ir.ui.menu', ('name',)),
    ('ir.model.field.access', ('field',)),
    ('ir.rule.group', ('name',)),
    ('ir.sequence', ('code', 'name')),
    ('res.user', ('login',)),
    ('ir.action', ('type', 'name')),
    ('ir.action.keyword', ('keyword',)),
    ('res.user.warning', ('name', 'user')),
    ('ir.rule', ('domain',)),
    ('ir.model.access', ('group.name', 'model.model')),
])
