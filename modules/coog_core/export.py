# -*- coding: utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64
import datetime
import collections
import json
import logging

from sql.operators import Concat

from trytond.pyson import Eval
from trytond.protocols.jsonrpc import JSONEncoder, JSONDecoder
from trytond.model import ModelSQL, ModelView, fields as tryton_fields
from trytond.model import Unique
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.server_context import ServerContext

import fields
import coog_string
from historizable import Historizable

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
    'ExportConfiguration',
    'ExportModelConfiguration',
    'ExportFieldConfiguration',
    'ExportModelExportConfigurationRelation',
    'ExportSelectFields',
    'ExportFieldsSelection',
    'ExportToFile',
    'ExportSummary',
    'ExportConfigurationSelection',
    ]


class NotExportImport(Exception):
    pass


class ExportImportMixin(Historizable):
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
        cls.__rpc__['import_json'] = RPC(readonly=False, result=lambda r: None)
        cls.__rpc__['export_json_to_file'] = RPC(instantiate=0,
            readonly=True, result=lambda r: cls._export_format_result(r))
        cls.__rpc__['ws_consult'] = RPC(readonly=True)
        cls.__rpc__['ws_create_objects'] = RPC(readonly=False)
        cls._export_binary_fields = set()

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
        cursor = Transaction().connection.cursor()
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
    def _allow_update_links_on_xml_rec(cls):
        return False

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

    @classmethod
    def _diff_skip(cls):
        # A list of fields which will not be exported during diff
        return cls._export_skips()

    def _export_filename(self):
        if (hasattr(self, 'code') and self.code):
            return self.code
        return self.get_rec_name(None)

    def _export_filename_prefix(self):
        return '[%s][%s]' % (datetime.date.today().isoformat(), self.__name__)

    def export_json_to_file(self, configuration=None):
        filename = '%s%s.json' % (self._export_filename_prefix(),
            self._export_filename())
        result = []
        already_exported = set()
        self.export_json(output=result, already_exported=already_exported,
            configuration=configuration)
        export_log = '<div>The following records will be exported:</div>'
        instances = collections.defaultdict(list)
        for value in already_exported:
            instances[value.__name__].append((value.rec_name,
                getattr(value, value._func_key)))
        for k, v in instances.iteritems():
            export_log += '<div><b>%s</b></div>' % k
            for elem in v:
                export_log += '<div>    %s - %s</div>' % elem
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
    def keep_existing_line(cls, field_name):
        return False

    @classmethod
    def _import_json(cls, values, main_object=None):
        logging.getLogger('import').debug('Importing [%s] %s' % (
                cls.__name__, values['_func_key']))
        cls.decode_binary_data(values)
        pool = Pool()
        new_values = {}
        lines = {}
        for field_name, value in values.iteritems():
            if field_name in ('__name__', '_func_key'):
                continue
            field = cls._fields[field_name]
            if isinstance(field, tryton_fields.MultiValue):
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
                        to_add.append(Target.import_json(line))
                        continue
                    obj_to_create = Target._import_json(line, None)
                    if obj_to_create:
                        to_create.append(obj_to_create)
            if existing_lines and not cls.keep_existing_line(field_name):
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

        logging.getLogger('import').debug(' -> done [%s] %s' % (
                cls.__name__, values['_func_key']))
        return new_values

    @classmethod
    def import_json(cls, values):
        import_data = ServerContext().get('_import_data', None)
        if import_data is None:
            import_data = {}
            with ServerContext().set_context(_import_data=import_data):
                return cls.import_json(values)

        pool = Pool()
        was_list = True
        if isinstance(values, basestring):
            values = json.loads(values, object_hook=JSONDecoder())
        if isinstance(values, dict):
            was_list = False
            values['__name__'] = cls.__name__
            values = [values]

        for value in values:
            if (value.get('_func_key', None) and
                    (value['__name__'], value['_func_key']) in import_data):
                continue
            ValueModel = pool.get(value['__name__'])
            existing = ValueModel.search_for_export_import(value)
            if len(existing) > 1:
                cls.raise_user_error('export_not_unique',
                    ('\n'.join([(x.__name__ + ' with id ' + str(x.id))
                                for x in existing]),
                        value['_func_key']))
            import_data[(value['__name__'], value['_func_key'])] = {
                'imported': False,
                'record': existing[0] if existing else None,
                'data': value,
                }

        results = []
        for value in values:
            data = import_data[(value['__name__'], value['_func_key'])]
            results.append(pool.get(value['__name__']).do_import(data))

        return results if was_list else results[0]

    @classmethod
    def do_import(cls, value):
        if value['imported']:
            return value['record']
        record = value['record']
        if record and (not cls.check_xml_record([record], None) and
                not cls._allow_update_links_on_xml_rec()):
            return record
        new_values = cls._import_json(value['data'], record)
        value['imported'] = True
        if not new_values:
            # The export is light
            if record:
                return record
            else:
                cls.raise_user_error('export_not_found', (cls.__name__,
                        value['data']['_func_key']))

        if record:
            cls.write([record], new_values)
        else:
            records = cls.create([new_values])
            record = records[0]
            value['record'] = record
        return record

    def export_master(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        if self.is_master_object():
            if self not in already_exported:
                self.export_json(skip_fields, already_exported, output,
                    main_object, configuration)
            return {'_func_key': getattr(self, self._func_key),
                '__name__': self.__name__}

    def _export_json_xxx2one(self, field_name, skip_fields=None,
            already_exported=None, output=None, main_object=None,
            configuration=None):
        target = getattr(self, field_name)
        if target is None:
            return None
        if not hasattr(target, 'export_json'):
            raise NotExportImport('%s is not exportable' % target)
        if target:
            values = target.export_master(skip_fields, already_exported,
                output, main_object, configuration)
            if values is None:
                values = target.export_json(skip_fields, already_exported,
                    output, main_object, configuration)
            return values

    def _export_json_xxx2many(self, field_name, skip_fields=None,
            already_exported=None, output=None, main_object=None,
            configuration=None):
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
                main_object, configuration)
            if not values:
                values = t.export_json(skip_fields, already_exported,
                    output, main_object, configuration)
            if values:
                results.append(values)
        return results

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        if not main_object:
            main_object = self
        if not configuration:
            skip_fields = (skip_fields or set()) | self._export_skips()
        else:
            skip_fields = (skip_fields or set())
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
        logging.getLogger('export').debug('Importing [%s] %s' % (
                self.__name__, values['_func_key']))
        light_exports = self._export_light()

        if configuration:
            model_configuration = configuration.get_model_configuration(
                self.__name__)
        else:
            model_configuration = None

        for field_name, field in self._fields.iteritems():
            if isinstance(field, tryton_fields.MultiValue):
                field = field._field
            if field_name in skip_fields:
                continue
            if (model_configuration and
                    field_name not in model_configuration['light'] and
                    field_name not in model_configuration['complete']):
                continue
            if (isinstance(field, tryton_fields.Function) and not
                    isinstance(field, tryton_fields.MultiValue) and
                    not configuration):
                continue
            if ((field_name in light_exports and not model_configuration) or
                    model_configuration and
                    field_name in model_configuration['light']):
                field_value = getattr(self, field_name)
                if (isinstance(field, (tryton_fields.One2Many,
                            tryton_fields.Many2Many)) or
                        isinstance(field, tryton_fields.Function) and
                        field._type in ('one2many', 'many2many')):
                    values[field_name] = [
                        {'_func_key': getattr(x, x._func_key)}
                        for x in field_value]
                elif (isinstance(field, tryton_fields.Reference) or
                        isinstance(field, tryton_fields.Function) and
                        field._type == 'reference'):
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
            elif (isinstance(field, (tryton_fields.Many2One,
                        tryton_fields.One2One, tryton_fields.Reference)) or
                    isinstance(field, tryton_fields.Function) and
                    field._type in ('many2one', 'one2one', 'reference')):
                values[field_name] = self._export_json_xxx2one(
                    field_name, None, already_exported, output,
                    main_object, configuration)
            elif (isinstance(field, (tryton_fields.One2Many,
                        tryton_fields.Many2Many)) or
                    isinstance(field, tryton_fields.Function) and
                    field._type in ('one2many', 'many2many')):
                values[field_name] = self._export_json_xxx2many(
                    field_name, None, already_exported, output,
                    main_object, configuration)
            else:
                values[field_name] = getattr(self, field_name)
        if output is not None and (
                self.is_master_object() or main_object == self):
            output.append(values)
        self.encode_binary_data(values, configuration)
        logging.getLogger('export').debug(' -> done [%s] %s' % (
                self.__name__, values['_func_key']))
        return values

    @classmethod
    def ws_consult(cls, objects, configuration_code=None):
        pool = Pool()
        ExportConfiguration = pool.get('ir.export.configuration')
        message = {}
        conf = None
        if configuration_code:
            configurations = ExportConfiguration.search([
                    ('code', '=', configuration_code)])
            if configurations:
                conf = configurations[0]
            else:
                cls.raise_user_error('missing_export_configuration',
                    configuration_code,
                    error_description='missing_export_configuration')
        for ext_id, values in objects.iteritems():
            try:
                possible_objects = cls.search_for_export_import(values)
                if not possible_objects:
                    cls.raise_user_error('No object found')
                elif len(possible_objects) >= 2:
                    cls.raise_user_error('Too many possibles objects')
                object_values = []
                if conf:
                    possible_objects[0].export_json(output=object_values,
                        configuration=conf)
                else:
                    possible_objects[0].export_json(output=object_values)
                message[ext_id] = {
                    'return': True,
                    'values': object_values,
                    }
            except UserError as exc:
                Transaction().rollback()
                message[ext_id] = {
                    'return': False,
                    'error': exc.message}
        return message

    @classmethod
    def ws_create_objects(cls, objects):
        """ Import a list of objects and returns a confirmation message.

        :param objects: a structure like so:
                        {
                            "any_exterior_id":
                                {
                                    "attribute_x": "the_value",
                                    "attribute_y": "the_value",
                                    etc..
                                },
                                etc ...
                        }
        """
        return_values = {}
        for ext_id, to_create in objects.iteritems():
            try:
                entity = cls.import_json(to_create)
            except UserError as exc:
                Transaction().rollback()
                return {ext_id: {
                        'return': False,
                        'messages': {'error': exc.message},
                        }}
            return_values[ext_id] = {'return': True,
                'messages': {cls.__name__: getattr(entity, getattr(
                            entity, '_func_key'))}}
        return return_values

    @classmethod
    def decode_binary_data(cls, values):
        for fname in cls._export_binary_fields:
            if fname in values:
                if values[fname]:
                    values[fname] = base64.b64decode(values[fname])

    def encode_binary_data(self, new_values, configuration):
        for fname in self._export_binary_fields:
            val = getattr(self, fname, None)
            if not configuration and val or fname in new_values:
                new_values[fname] = base64.b64encode(val) if val else val


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
                result += '<div><b>%s</b></div>' % k
                for elem in v:
                    result += '<div>    %s</div>' % elem
            return result


class ImportWizard(Wizard):
    'Import Wizard'

    __name__ = 'ir.import'

    start_state = 'file_selector'
    file_selector = StateView('ir.import.select_file',
        'coog_core.import_select_file_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Import', 'file_import', 'tryton-ok')])
    file_import = StateTransition()

    def transition_file_import(self):
        if not (hasattr(self.file_selector, 'selected_file') and
                self.file_selector.selected_file):
            self.raise_user_error('no_file_selected')
        file_buffer = self.file_selector.selected_file
        values = str(file_buffer)
        ExportImportMixin.import_json(values)
        return 'end'


class ExportInstance(ExportImportMixin, ModelView):
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


class ExportPackage(ExportImportMixin, ModelView):
    'Export Package'

    __name__ = 'ir.export_package'
    _rec_name = 'package_name'
    _func_key = 'code'

    code = fields.Char('Code', required=True, select=True)
    package_name = fields.Char('Package Name', required=True, translate=True)
    instances_to_export = fields.One2Many('ir.export_package.item', 'package',
        'Instances to export')

    @classmethod
    def __setup__(cls):
        super(ExportPackage, cls).__setup__()
        cls._order = [
            ('code', 'ASC'),
            ]

    @fields.depends('code', 'package_name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.package_name)

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = values['package_name']


class Add2ExportPackageWizardStart(ModelView):
    'Export Package Selector'
    __name__ = 'ir.export_package.add_records.start'

    export_package = fields.Many2One('ir.export_package', 'Package',
        required=True)


class Add2ExportPackageWizard(Wizard):
    'Wizard to add records to Export Packages'

    __name__ = 'ir.export_package.add_records'

    start = StateView('ir.export_package.add_records.start',
        'coog_core.ir_export_package_add_records_start', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Add', 'add', 'tryton-ok', default=True),
            ])
    add = StateTransition()

    def transition_add(self):
        pool = Pool()
        ExportPackageItem = pool.get('ir.export_package.item')
        ids = Transaction().context['active_ids']
        model = Transaction().context['active_model']
        ExportPackageItem.create([{
                    'to_export': '%s,%s' % (model, id_),
                    'package': self.start.export_package,
                    } for id_ in ids])
        return 'end'


class ExportConfiguration(ExportImportMixin, ModelView):
    'Export Configuration'
    __name__ = 'ir.export.configuration'
    _func_key = 'code'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    models_configuration = fields.Many2Many(
        'ir.export_configuration-export_model', 'configuration', 'model',
        'Models Configuration')

    @classmethod
    def __setup__(cls):
        super(ExportConfiguration, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]

    @property
    def configuration(self):
        if not getattr(self, '_configuration', None):
            self.init_configuration()
        return self._configuration

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def init_configuration(self):
        self._configuration = {}
        for model_configuration in self.models_configuration:
            self._configuration[model_configuration.model.model] = \
                model_configuration.get_fields()

    def get_model_configuration(self, model_name):
        conf = self.configuration
        if model_name in conf:
            return conf[model_name]
        return None


class ExportModelConfiguration(ExportImportMixin, ModelView):
    'Export Model Configuration'
    __name__ = 'ir.export.configuration.model'

    name = fields.Char('Name', required=True, translate=True)
    code = fields.Char('Code', required=True)
    model = fields.Function(fields.Many2One('ir.model', 'Model',
            required=True),
        'get_model', setter='set_model')
    model_name = fields.Char('Model Name')
    fields_configuration = fields.One2Many('ir.export.configuration.field',
        'model', 'Model Configuration')

    @classmethod
    def __setup__(cls):
        super(ExportModelConfiguration, cls).__setup__()
        t = cls.__table__()
        cls._sql_constraints += [
            ('code_uniq', Unique(t, t.code), 'The code must be unique!'),
            ]
        cls._buttons.update({
                'button_select_fields': {},
                })

    def get_model(self, name):
        pool = Pool()
        Model = pool.get('ir.model')
        if self.model_name:
            the_model, = Model.search([('model', '=', self.model_name)])
            return the_model.id

    @classmethod
    def set_model(cls, configurations, name, value):
        pool = Pool()
        Model = pool.get('ir.model')
        if value:
            model = Model(value)
            cls.write(configurations, {'model_name': model.model})
        else:
            cls.write(configurations, {'model_name': ''})

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coog_string.slugify(self.name)

    def get_fields(self):
        res = collections.defaultdict(list)
        for field in self.fields_configuration:
            if field.export_light_strategy:
                res['light'].append(field.field_name)
            else:
                res['complete'].append(field.field_name)
        return res

    @classmethod
    def _export_light(cls):
        return (super(ExportModelConfiguration, cls)._export_light() |
            set(['model']))

    @classmethod
    @ModelView.button_action('coog_core.export_fields_selection')
    def button_select_fields(cls, export_models):
        pass


class ExportFieldConfiguration(ExportImportMixin, ModelView):
    'Export Field Configuration'
    __name__ = 'ir.export.configuration.field'
    _rec_name = 'field_name'

    model = fields.Many2One('ir.export.configuration.model',
        'Model Configuration', required=True, ondelete='CASCADE')
    field_model = fields.Function(
        fields.Many2One('ir.model.field', 'Model Field', required=True),
        'get_field_model')
    field_name = fields.Char('Field Name')
    is_relation_field = fields.Function(
        fields.Boolean('Is A Relation Field'),
        'get_is_relation_field')
    export_light_strategy = fields.Boolean('Export Light',
        depends=['is_relation_field', 'field_model'],
        states={'invisible': ~Eval('is_relation_field')})

    @classmethod
    def __setup__(cls):
        super(ExportFieldConfiguration, cls).__setup__()
        cls._error_messages.update({
                'wrong_field_name': 'Field %s is not defined in model %s'
                })

    def get_field_model(self, name):
        pool = Pool()
        FieldModel = pool.get('ir.model.field')
        if self.field_name:
            the_field, = FieldModel.search([
                    ('name', '=', self.field_name),
                    ('model', '=', self.model.model.id)])
            return the_field.id

    def get_is_relation_field(self, name):
        if self.field_model:
            return self.field_model.ttype in ('many2one', 'many2many',
                'one2many', 'one2one', 'reference')


class ExportModelExportConfigurationRelation(ModelSQL):
    'Relation between export configuration and export model'
    __name__ = 'ir.export_configuration-export_model'

    configuration = fields.Many2One('ir.export.configuration',
        'Export Configuration', ondelete='CASCADE')
    model = fields.Many2One('ir.export.configuration.model', 'Export Model',
        ondelete='RESTRICT')


class ExportSelectFields(ModelView):
    'Select Export Fields'
    __name__ = 'export.fields.select'

    available_fields = fields.One2Many('ir.model.field', None,
        'Available Fields')
    selected_fields = fields.Many2Many('ir.model.field', None, None,
        'Selected Fields', domain=[('id', 'in', Eval('available_fields'))],
        depends=['available_fields'])


class ExportFieldsSelection(Wizard):
    'Fields Selection Wizard'
    __name__ = 'export.fields.selection'

    start_state = 'fields_selection'
    fields_selection = StateView('export.fields.select',
        'coog_core.export_fields_select_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply', 'tryton-go-next')])
    apply = StateTransition()

    def get_export_model(self):
        pool = Pool()
        ExportModel = pool.get('ir.export.configuration.model')
        return ExportModel(Transaction().context.get('active_id'))

    def default_fields_selection(self, name):
        export_model = self.get_export_model()
        return {'available_fields': [x.id for x in export_model.model.fields]}

    def transition_apply(self):
        pool = Pool()
        ExportField = pool.get('ir.export.configuration.field')
        export_model = self.get_export_model()
        ExportModel = pool.get(export_model.model.model)
        export_fields = []
        light = ExportModel._export_light()
        for field in self.fields_selection.selected_fields:
            if field.name in light:
                is_light = True
            else:
                is_light = False
            export_fields.append(ExportField(
                    field_name=field.name,
                    model=export_model,
                    export_light_strategy=is_light)
                )
        ExportField.create([x._save_values for x in export_fields])
        return 'end'


class ExportConfigurationSelection(ModelView):
    'Export Configuration Selection'
    __name__ = 'export.export_configuration_selection'

    configuration = fields.Many2One('ir.export.configuration', 'Configuration',
        None)
    beautify_output = fields.Boolean('Beautify output file')


class ExportSummary(ModelView):
    'Export Summary'
    __name__ = 'export.export_summary'

    summary = fields.Text('Export Summary', readonly=True)
    file = fields.Binary('Export File', filename='file_name', readonly=True)
    file_name = fields.Char('File Name')


class ExportToFile(Wizard):
    'Export To File Wizard'
    __name__ = 'export.export_to_file'

    start_state = 'conf_selection'
    conf_selection = StateView('export.export_configuration_selection',
        'coog_core.export_configuration_selection_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Next', 'export', 'tryton-go-next')])
    export = StateTransition()
    export_summary = StateView('export.export_summary',
        'coog_core.export_summary_view_form', [
            Button('Previous', 'conf_selection', 'tryton-go-previous'),
            Button('Ok', 'end', 'tryton-ok')])

    def default_conf_selection(self, name):
        return {'beautify_output': False}

    def transition_export(self):
        pool = Pool()
        model = Transaction().context.get('active_model')
        Model = pool.get(model)
        model_id = Transaction().context.get('active_id')
        export_object = Model(model_id)
        file_name, result, summary = export_object.export_json_to_file(
                self.conf_selection.configuration)
        if self.conf_selection.beautify_output:
            result = json.dumps(result, cls=JSONEncoder, indent=4,
                    sort_keys=True, separators=(',', ': '))
        else:
            result = json.dumps(result, cls=JSONEncoder)
        self.export_summary.summary = summary
        self.export_summary.file = result
        self.export_summary.file_name = file_name
        return 'export_summary'

    def default_export_summary(self, name):
        return {
            'summary': self.export_summary.summary,
            'file': self.export_summary.file,
            'file_name': self.export_summary.file_name,
            }
