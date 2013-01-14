import copy

from itertools import chain
try:
    import simplejson as json
except ImportError:
    import json

from trytond.pyson import Eval, Bool
from trytond.model import ModelView, ModelSQL, fields as fields
from trytond.wizard import Wizard
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.rpc import RPC
from trytond.protocols.jsonrpc import JSONEncoder, object_hook

import utils
from trytond.modules.coop_utils import coop_string


class NotExportImport(Exception):
    pass


class ExportImportMixin(object):
    'Mixin to support export/import in json'
    __metaclass__ = PoolMeta

    _export_name = 'rec_name'

    @classmethod
    def __setup__(cls):
        super(ExportImportMixin, cls).__setup__()
        cls.__rpc__['export_json'] = RPC(instantiate=0,
            result=lambda r: json.dumps(r, cls=JSONEncoder))
        cls.__rpc__['import_json'] = RPC(readonly=False,
            result=lambda r: None)

    def _export_json_xxx2one(self, field_name, skip_fields=None):
        target = getattr(self, field_name)
        if not hasattr(target, 'export_json'):
            raise NotExportImport()
        if target:
            return target.export_json(skip_fields=skip_fields)

    def _export_json_xxx2many(self, field_name, skip_fields=None):
        if skip_fields is None:
            skip_fields = set()
        field = self._fields[field_name]
        if isinstance(field, fields.One2Many):
            skip_fields.add(field.field)
        if not hasattr(field.get_target(), 'export_json'):
            raise NotExportImport()
        targets = getattr(self, field_name) or []
        return [t.export_json(skip_fields=skip_fields) for t in targets]

    def export_json(self, skip_fields=None):
        if skip_fields is None:
            skip_fields = set()
        skip_fields |= set(('id',
                'create_uid', 'write_uid',
                'create_date', 'write_date'))
        values = {
            '__name__': self.__name__,
            '_export_name': getattr(self, self._export_name),
            }
        for field_name, field in self._fields.iteritems():
            if (field_name in skip_fields
                    or (isinstance(field, fields.Function)
                        and not isinstance(field, fields.Property))):
                continue
            elif isinstance(field, (fields.Many2One, fields.One2One,
                        fields.Reference)):
                try:
                    values[field_name] = self._export_json_xxx2one(field_name)
                except NotExportImport:
                    pass
            elif isinstance(field, (fields.One2Many, fields.Many2Many)):
                try:
                    values[field_name] = self._export_json_xxx2many(field_name)
                except NotExportImport:
                    pass
            else:
                values[field_name] = getattr(self, field_name)
        return values

    @classmethod
    def _import_json(cls, values):
        pool = Pool()
        assert values['__name__'] == cls.__name__, (values['__name__'],
            cls.__name__)
        new_values = {}
        lines = {}
        for field_name, value in values.iteritems():
            if field_name in ('__name__', '_export_name'):
                continue
            field = cls._fields[field_name]
            if isinstance(field, (fields.Many2One, fields.One2One,
                        fields.Reference)):
                if value:
                    if isinstance(field, fields.Reference):
                        Target = pool.get(value['__name__'])
                    else:
                        Target = field.get_target()
                    target = Target.import_json(value)
                    new_values[field_name] = target.id
                else:
                    new_values[field_name] = None
            elif isinstance(field, (fields.One2Many, fields.Many2Many)):
                lines[field_name] = value
            else:
                new_values[field_name] = value

        if cls.recreate_rather_than_update():
            record = None
        else:
            records = cls.search(
                [(cls._export_name, '=', values['_export_name'])])
            if records:
                if len(records) > 1:
                    pass
                    print 'Too many values found for class %s (%s)' % (
                        cls._export_name, values['_export_name'])
                record, = records
            else:
                record = None

        for field_name, value in lines.iteritems():
            field = cls._fields[field_name]
            Target = field.get_target()
            if record:
                existing_lines = dict((getattr(l, l._export_name), l)
                    for l in getattr(record, field_name))
            else:
                existing_lines = {}

            writes = []
            creates = []
            adds = []
            deletes = []
            for line in value:
                export_name = line['_export_name']
                if export_name in existing_lines:
                    existing_line = existing_lines[export_name]
                    writes.append(
                        ('write', [existing_line.id],
                            Target._import_json(line)))
                    del existing_lines[export_name]
                else:
                    if isinstance(field, fields.Many2Many):
                        if Target.search([
                                    (Target._export_name, '=',
                                        line['_export_name'])]):
                            target = Target.import_json(line)
                            adds.append(target.id)
                            continue
                    creates.append(
                        ('create', Target._import_json(line)))
            if existing_lines:
                deletes.append(
                    ('delete', [l.id for l in existing_lines.itervalues()]))

            new_values[field_name] = []
            for action in (writes, creates, deletes):
                if action:
                    new_values[field_name].extend(action)
            if adds:
                new_values[field_name].append(('add', adds))

        return new_values

    @classmethod
    def import_json(cls, values):
        if isinstance(values, basestring):
            values = json.loads(values, object_hook=object_hook)
        new_values = cls._import_json(values)
        records = cls.search([(cls._export_name, '=', values['_export_name'])])
        if records:
            record, = records
            cls.write(records, new_values)
        else:
            record = cls.create(new_values)
        return record

    @classmethod
    def recreate_rather_than_update(cls):
        return False


class CoopSQL(ExportImportMixin, ModelSQL):
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
                        translate_model_name(using_instance.__class__),
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

    def get_rec_name(self, name):
        res = ''
        if hasattr(self, 'code'):
            res = '%s' % getattr(self, 'code')
        return coop_string.concat_strings(
            res, super(CoopSQL, self).get_rec_name(name))


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


class One2ManyDomain(fields.One2Many):

    def get(self, ids, model, name, values=None):
        '''
        Return target records ordered.
        '''
        pool = Pool()
        Relation = pool.get(self.model_name)
        if self.field in Relation._fields:
            field = Relation._fields[self.field]
        else:
            field = Relation._inherit_fields[self.field][2]
        res = {}
        for i in ids:
            res[i] = []

        targets = []
        for i in range(0, len(ids), Transaction().cursor.IN_MAX):
            sub_ids = ids[i:i + Transaction().cursor.IN_MAX]
            if field._type == 'reference':
                references = ['%s,%s' % (model.__name__, x) for x in sub_ids]
                clause = [(self.field, 'in', references)]
            else:
                clause = [(self.field, 'in', sub_ids)]
            clause.append(self.domain)
            targets.append(Relation.search(clause, order=self.order))
        targets = list(chain(*targets))

        for target in targets:
            origin_id = getattr(target, self.field).id
            res[origin_id].append(target.id)
        return dict((key, tuple(value)) for key, value in res.iteritems())


class VersionedObject(CoopView):
    'Versionned Object'

    __name__ = 'utils.versionned_object'

    versions = fields.One2Many(
        None,
        'main_elem',
        'Versions')
    current_rec_name = fields.Function(fields.Char('Current Value'),
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

    main_elem = fields.Many2One(
        None,
        'Descriptor',
        ondelete='CASCADE')
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
