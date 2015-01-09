# -*- coding: utf-8 -*-
import copy
import datetime
import collections
try:
    import simplejson as json
except ImportError:
    import json

from sql.operators import Concat

from trytond.protocols.jsonrpc import JSONEncoder, JSONDecoder
from trytond.model import Model, ModelSQL, ModelView, fields as tryton_fields
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.exceptions import UserError
from trytond.transaction import Transaction

import fields
import coop_string

__metaclass__ = PoolMeta
__all__ = [
    'NotExportImport',
    'ExportImportMixin',
    'FileSelector',
    'ImportWizard',
    'ExportInstance',
    'ExportPackage',
    'Add2ExportPackageWizard',
    'Add2ExportPackageWizardStart',
    ]


class NotExportImport(Exception):
    pass


class ExportImportMixin(Model):
    'Mixin to support export/import in json'

    _func_key = 'rec_name'

    xml_id = fields.Function(
        fields.Char('XML Id', states={'invisible': True}),
        'get_xml_id', searcher='search_xml_id')

    def get_publishing_values(self):
        # Returns a dictionary with all strings that may be used when
        # publishing.
        return {}

    @property
    def _ed(self):
        return self.get_publishing_values()

    @classmethod
    def __setup__(cls):
        super(ExportImportMixin, cls).__setup__()
        cls.__rpc__['export_json'] = RPC(instantiate=0,
            result=lambda r: cls._export_format_result(r))
        cls.__rpc__['import_json'] = RPC(readonly=False, result=lambda r: None)
        cls.__rpc__['export_json_to_file'] = RPC(instantiate=0,
            readonly=True, result=lambda r: cls._export_format_result(r))
        cls.__rpc__['multiple_import_json'] = RPC(readonly=False,
            result=lambda r: None)
        cls.__rpc__['ws_consult'] = RPC(readonly=True)
        cls._error_messages.update({
                'not_found': 'Cannot import : no object %s with functional '
                'key: "%s" were found.',
                'not_unique': 'Cannot import : the following objects:\n%s\n'
                'share the same functional key:\n"%s".',
                })

    @classmethod
    def __post_setup__(cls):
        super(ExportImportMixin, cls).__post_setup__()
        if not hasattr(cls, '_fields'):
            return
        for field_name, field in cls._fields.iteritems():
            if not field.required:
                continue
            tmp_field = copy.copy(field)
            tmp_field.required = False
            if not tmp_field.states:
                tmp_field.states = {}
            if ('required' in tmp_field.states and
                    tmp_field.states['required'] and tmp_field.required):
                raise Exception('\'required\' attribute defined both in field '
                    'definition and states for field %s in model %s' % (
                        field_name, cls.__name__))
            tmp_field.states['required'] = True
            setattr(cls, field_name, tmp_field)

    @classmethod
    def get_xml_id(cls, objects, name):
        ModelData = Pool().get('ir.model.data')
        values = ModelData.search([
                ('model', '=', cls.__name__),
                ('db_id', 'in', [x.id for x in objects])])
        result = collections.defaultdict(lambda: '')
        result.update(dict([(x.db_id, '%s.%s' % (x.module, x.fs_id))
                    for x in values]))
        return result

    @classmethod
    def search_xml_id(cls, name, clause):
        cursor = Transaction().cursor
        _, operator, value = clause
        Operator = tryton_fields.SQL_OPERATORS[operator]
        ModelData = Pool().get('ir.model.data')
        model_table = ModelData.__table__()

        cursor.execute(*model_table.select(model_table.db_id,
                where=((model_table.model == cls.__name__)
                    & Operator(Concat(model_table.module,
                            Concat('.', model_table.fs_id)),
                        getattr(cls, name).sql_format(value)))))
        return [('id', 'in', [x[0] for x in cursor.fetchall()])]

    @classmethod
    def _export_format_result(cls, result):
        return (result[0], json.dumps(result[1], cls=JSONEncoder, indent=4,
                sort_keys=True, separators=(',', ': ')), result[2])

    @classmethod
    def _export_skips(cls):
        # A list of fields which will not be exported
        return set(('id', 'create_uid', 'write_uid', 'create_date',
                'write_date'))

    @classmethod
    def _export_light(cls):
        # A list of fields which will not be recursively exported.
        return set()

    def _export_filename(self):
        if (hasattr(self, 'code') and self.code):
            return self.code
        return self.get_rec_name(None)

    def _export_filename_prefix(self):
        return '[%s][%s]' % (datetime.date.today().isoformat(), self.__name__)

    def export_json_to_file(self):
        filename = '%s%s.json' % (self._export_filename_prefix(),
            self._export_filename())
        result = []
        already_exported = set()
        self.export_json(output=result, already_exported=already_exported)
        export_log = 'The following records will be exported:\n '
        instances = collections.defaultdict(list)
        for value in already_exported:
            instances[value.__name__].append((value.rec_name,
                getattr(value, value._func_key)))
        for k, v in instances.iteritems():
            export_log += '<b>%s</b>\n' % k
            for elem in v:
                export_log += '    %s - %s\n' % elem
        return filename, result, export_log

    @classmethod
    def is_master_object(cls):
        return False

    @classmethod
    def add_func_key(cls, values):
        '''
        The aim of this method is to add the _func_key in dictionnary
        if missing to avoid sender filling _func_key
        '''
        raise NotImplementedError

    @classmethod
    def search_for_export_import(cls, values):
        '''
        The method is used to find existing object from values
        By default it's searching based on the _func_key
        '''
        if '_func_key' not in values:
            cls.add_func_key(values)
        return cls.search([(cls._func_key, '=', values['_func_key'])])

    @classmethod
    def get_existing_lines(cls, main_object, field_name):
        return dict((getattr(l, l._func_key), l)
                    for l in getattr(main_object, field_name))

    @classmethod
    def _import_json(cls, values, main_object=None):
        pool = Pool()
        new_values = {}
        lines = {}
        for field_name, value in values.iteritems():
            if field_name in ('__name__', '_func_key'):
                continue
            field = cls._fields[field_name]
            if isinstance(field, tryton_fields.Property):
                field = field._field
            if isinstance(field, (tryton_fields.Many2One,
                        tryton_fields.One2One, tryton_fields.Reference)):
                if value:
                    if isinstance(field, tryton_fields.Reference):
                        Target = pool.get(value['__name__'])
                    else:
                        Target = field.get_target()
                    target = Target.import_json(value)
                    if not target:
                        continue
                    if isinstance(field, tryton_fields.Reference):
                        new_values[field_name] = (target.__name__ +
                            ',' + str(target.id))
                    else:
                        new_values[field_name] = target.id
                else:
                    new_values[field_name] = None
            elif isinstance(field, (tryton_fields.One2Many,
                    tryton_fields.Many2Many)):
                lines[field_name] = value
            else:
                new_values[field_name] = value

        for field_name, value in lines.iteritems():
            field = cls._fields[field_name]
            Target = field.get_target()
            if main_object:
                existing_lines = cls.get_existing_lines(main_object,
                    field_name)
            else:
                existing_lines = {}
            to_write = []
            to_create = []
            to_add = []
            to_delete = []
            to_remove = []
            for line in value:
                if '_func_key' not in line:
                    Target.add_func_key(line)
                export_name = line['_func_key']
                if export_name in existing_lines:
                    existing_line = existing_lines[export_name]
                    to_write.append(
                        ('write', [existing_line.id],
                            Target._import_json(line,
                                Target(existing_line.id))))
                    del existing_lines[export_name]
                else:
                    if isinstance(field, tryton_fields.Many2Many):
                        # One2many to master object are not managed
                        if Target.search_for_export_import(line):
                            target = Target.import_json(line)
                            to_add.append(target.id)
                            continue
                    obj_to_create = Target._import_json(line, None)
                    if obj_to_create:
                        to_create.append(obj_to_create)
            if existing_lines:
                if isinstance(field, tryton_fields.Many2Many):
                    to_remove.append(
                        ('remove', [l.id for l in
                                existing_lines.itervalues()]))
                else:
                    to_delete.append(
                        ('delete', [l.id for l in
                                existing_lines.itervalues()]))

            new_values[field_name] = []
            if to_create:
                to_create = [('create', to_create)]
            for action in (to_write, to_create, to_delete, to_remove):
                if action:
                    new_values[field_name].extend(action)
            if to_add:
                new_values[field_name].append(('add', to_add))

        return new_values

    @classmethod
    def multiple_import_json(cls, objects):
        pool = Pool()
        if isinstance(objects, basestring):
            objects = json.loads(objects, object_hook=JSONDecoder())
        for obj in objects:
            Target = pool.get(obj['__name__'])
            Target.import_json(obj)

    @classmethod
    def import_json(cls, values):
        if isinstance(values, basestring):
            values = json.loads(values, object_hook=JSONDecoder())
        records = cls.search_for_export_import(values)
        record = None
        if records:
            if len(records) > 1:
                cls.raise_user_error('not_unique',
                    ('\n'.join([(x.__name__ + ' with id ' + str(x.id))
                                for x in records]),
                        values['_func_key']))
            record = (records or [None])[0]
        new_values = cls._import_json(values, record)

        if not new_values:
            # The export is light
            if record:
                return record
            else:
                cls.raise_user_error('not_found', (cls.__name__,
                        values['_func_key']))

        if record:
            cls.write([record], new_values)
        else:
            records = cls.create([new_values])
            record = records[0]
        return record

    def export_master(self, skip_fields=None, already_exported=None,
            output=None, main_object=None):
        if self.is_master_object():
            if self not in already_exported:
                self.export_json(skip_fields, already_exported, output,
                    main_object)
            return {'_func_key': getattr(self, self._func_key),
                '__name__': self.__name__}

    def _export_json_xxx2one(self, field_name, skip_fields=None,
            already_exported=None, output=None, main_object=None):
        target = getattr(self, field_name)
        if target is None:
            return None
        if not hasattr(target, 'export_json'):
            raise NotExportImport('%s is not exportable' % target)
        if target:
            values = target.export_master(skip_fields, already_exported,
                output, main_object)
            if values is None:
                values = target.export_json(skip_fields, already_exported,
                    output, main_object)
            return values

    def _export_json_xxx2many(self, field_name, skip_fields=None,
            already_exported=None, output=None, main_object=None):
        if skip_fields is None:
            skip_fields = set()
        field = self._fields[field_name]
        if isinstance(field, tryton_fields.One2Many):
            skip_fields.add(field.field)
        Target = field.get_target()
        if Target is None:
            return None
        if not hasattr(Target, 'export_json'):
            raise NotExportImport('%s is not exportable'
                % Target)
        targets = getattr(self, field_name) or []
        results = []
        for t in targets:
            values = t.export_master(skip_fields, already_exported, output,
                main_object)
            if not values:
                values = t.export_json(skip_fields, already_exported,
                    output, main_object)
            if values:
                results.append(values)
        return results

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None):
        if not main_object:
            main_object = self
        skip_fields = (skip_fields or set()) | self._export_skips()
        values = {
            '__name__': self.__name__,
            '_func_key': getattr(self, self._func_key),
            }
        if already_exported and self in already_exported:
            return values
        elif already_exported is None:
            already_exported = set([self])
        else:
            already_exported.add(self)

        light_exports = self._export_light()

        for field_name, field in self._fields.iteritems():
            if isinstance(field, tryton_fields.Property):
                field = field._field
            if (field_name in skip_fields or
                    (isinstance(field, tryton_fields.Function) and not
                    isinstance(field, tryton_fields.Property))):
                continue
            elif field_name in light_exports:
                field_value = getattr(self, field_name)
                if isinstance(field, (tryton_fields.One2Many,
                            tryton_fields.Many2Many)):
                    values[field_name] = [
                        {'_func_key': getattr(x, x._func_key)}
                        for x in field_value]
                elif isinstance(field, tryton_fields.Reference):
                    if not field_value:
                        values[field_name] = None
                    else:
                        values[field_name] = {'_func_key': getattr(
                                field_value, field_value._func_key),
                            '__name__': field_value.__name__}
                else:
                    if not field_value:
                        values[field_name] = None
                    else:
                        values[field_name] = {'_func_key': getattr(
                            field_value, field_value._func_key)}
            elif isinstance(field, (tryton_fields.Many2One,
                        tryton_fields.One2One, tryton_fields.Reference)):
                values[field_name] = self._export_json_xxx2one(
                    field_name, None, already_exported, output,
                    main_object)
            elif isinstance(field, (tryton_fields.One2Many,
                        tryton_fields.Many2Many)):
                values[field_name] = self._export_json_xxx2many(
                    field_name, None, already_exported, output,
                    main_object)
            else:
                values[field_name] = getattr(self, field_name)
        if self.is_master_object() or main_object == self:
            output.append(values)
        return values

    @classmethod
    def ws_consult(cls, objects):
        message = {}
        for ext_id, values in objects.iteritems():
            try:
                possible_objects = cls.search_for_export_import(values)
                if not possible_objects:
                    cls.raise_user_error('No object found')
                elif len(possible_objects) >= 2:
                    cls.raise_user_error('Too many possibles objects')
                object_values = []
                possible_objects[0].export_json(output=object_values)
                message[ext_id] = {
                    'return': True,
                    'values': object_values,
                    }
            except UserError as exc:
                message[ext_id] = {
                    'return': False,
                    'error': exc.message}
        return message


class FileSelector(ModelView):
    'File Selector'

    __name__ = 'ir.import.select_file'

    selected_file = fields.Binary('Import File', filename='name')
    name = fields.Char('Filename')
    file_content = fields.Text('File Content')

    @fields.depends('selected_file')
    def on_change_with_file_content(self):
        if not (hasattr(self, 'selected_file') and self.selected_file):
            return ''
        else:
            file_buffer = self.selected_file
            values = str(file_buffer)
            values = json.loads(values, object_hook=JSONDecoder())
            instances = {}
            for value in values:
                if not value['__name__'] in instances:
                    instances[value['__name__']] = []
                instances[value['__name__']].append(value['_func_key'])
            result = ''
            for k, v in instances.iteritems():
                result += '<b>%s</b>\n' % k
                for elem in v:
                    result += '    %s\n' % elem
            return result


class ImportWizard(Wizard):
    'Import Wizard'

    __name__ = 'ir.import'

    start_state = 'file_selector'
    file_selector = StateView('ir.import.select_file',
        'cog_utils.import_select_file_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Import', 'file_import', 'tryton-ok')])
    file_import = StateTransition()

    def transition_file_import(self):
        if not (hasattr(self.file_selector, 'selected_file') and
                self.file_selector.selected_file):
            self.raise_user_error('no_file_selected')
        file_buffer = self.file_selector.selected_file
        values = str(file_buffer)
        ExportImportMixin.multiple_import_json(values)
        return 'end'


class ExportInstance(ExportImportMixin, ModelSQL, ModelView):
    'Export Instance'

    __name__ = 'ir.export_package.item'

    to_export = fields.Reference('To export', 'get_all_exportable_models',
        required=True)
    package = fields.Many2One('ir.export_package', 'Package',
        ondelete='CASCADE')

    @staticmethod
    def get_all_exportable_models():
        pool = Pool()
        Model = pool.get('ir.model')
        models = Model.search([])
        res = []
        for model in models:
            res.append([model.model, model.name])
        return res


class ExportPackage(ExportImportMixin, ModelSQL, ModelView):
    'Export Package'

    __name__ = 'ir.export_package'
    _rec_name = 'package_name'

    code = fields.Char('Code')
    package_name = fields.Char('Package Name', required=True)
    instances_to_export = fields.One2Many('ir.export_package.item', 'package',
        'Instances to export')

    @fields.depends('code', 'package_name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.package_name)


class Add2ExportPackageWizardStart(ModelView):
    'Export Package Selector'
    __name__ = 'ir.export_package.add_records.start'

    export_package = fields.Many2One('ir.export_package', 'Package',
        required=True)


class Add2ExportPackageWizard(Wizard):
    'Wizard to add records to Export Packages'

    __name__ = 'ir.export_package.add_records'

    start = StateView('ir.export_package.add_records.start',
        'cog_utils.ir_export_package_add_records_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add', 'tryton-ok'),
            ])
    add = StateTransition()

    def transition_add(self):
        pool = Pool()
        ExportPackageItem = pool.get('ir.export_package.item')
        ids = Transaction().context['active_ids']
        print Transaction().context
        model = Transaction().context['active_model']
        ExportPackageItem.create([{
                    'to_export': '%s,%s' % (model, id_),
                    'package': self.start.export_package,
                    } for id_ in ids])
        return 'end'
