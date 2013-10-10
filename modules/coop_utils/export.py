import traceback
import sys
import copy
import datetime
import logging
try:
    import simplejson as json
except ImportError:
    import json

from trytond.protocols.jsonrpc import JSONEncoder, object_hook
from trytond.model import Model, ModelSQL, ModelView, fields as tryton_fields
from trytond.model import ModelSingleton
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond import backend
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, PYSONEncoder

import utils
import fields

__all__ = [
    'NotExportImport',
    'ExportImportMixin',
    'FileSelector',
    'ImportWizard',
    'ExportInstance',
    'ExportPackage',
    'Group',
    'UIMenu',
    'add_export_to_model',
]


class NotExportImport(Exception):
    pass


class ExportImportMixin(Model):
    'Mixin to support export/import in json'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(ExportImportMixin, cls).__setup__()
        cls.__rpc__['export_json'] = RPC(
            instantiate=0,
            result=lambda r: (r[0], json.dumps(r[1], cls=JSONEncoder), r[2]))
        cls.__rpc__['import_json'] = RPC(
            readonly=False, result=lambda r: None)
        if not hasattr(cls, '_fields'):
            return
        for field_name, field in cls._fields.iteritems():
            if not field.required:
                continue
            tmp_field = copy.copy(field)
            tmp_field.required = False
            if not tmp_field.states:
                tmp_field.states = {}
            if 'required' in tmp_field.states and \
                    tmp_field.states['required'] and tmp_field.required:
                raise Exception('\'required\' attribute defined both in field '
                    'definition and states for field %s in model %s' % (
                        field_name, cls.__name__))
            tmp_field.states['required'] = True
            setattr(cls, field_name, tmp_field)

    @classmethod
    def __register__(cls, module_name):
        super(ExportImportMixin, cls).__register__(module_name)
        if not hasattr(cls, '_fields'):
            return
        cursor = Transaction().cursor
        try:
            table = backend.get('TableHandler')(cursor, cls, module_name)
        except AttributeError:
            # No _table defined for model
            return
        for field_name, field in cls._fields.iteritems():
            if (not 'required' in field.states or field.states['required'] is
                    not True):
                continue
            if not table.column_exist(field_name):
                continue
            if not table._columns[field_name]['notnull']:
                continue
            table.cursor.execute('ALTER TABLE "%s" '
                'ALTER COLUMN "%s" DROP NOT NULL'
                % (table.table_name, field_name))
            table._update_definitions()

    def _prepare_for_import(self):
        pass

    @classmethod
    def _post_import(cls, records):
        pass

    @classmethod
    def _export_keys(cls):
        # Returns a set of fields which will be used to compute a unique
        # functional key for self.
        # field_name may use "." to chain if it is not ambiguous
        # TODO : Look for a field with 'UNIQUE' and 'required' attributes set
        res = []
        if 'company' in cls._fields and (
                not isinstance(cls._fields['company'], tryton_fields.Function)
                or isinstance(cls._fields['company'], tryton_fields.Property)):
            res.append('company.party.name')
        if 'code' in cls._fields:
            return set(res + ['code'])
        elif 'name' in cls._fields:
            return set(res + ['name'])
        else:
            return set()

    @classmethod
    def _export_skips(cls):
        # A list of fields which will not be exported
        return set((
            'id', 'create_uid', 'write_uid', 'create_date', 'write_date'))

    @classmethod
    def _export_light(cls):
        # A list of fields which will not be recursively exported.
        return set()

    @classmethod
    def _export_force_recreate(cls):
        # A list of X2M fields which will be deleted then recreated rather than
        # updated. By default, all O2M fields are forced, as they usually
        # do not have a functional key.
        force = set()
        for field_name, field in cls._fields.iteritems():
            if isinstance(field, tryton_fields.One2Many):
                force.add(field_name)
        return force

    def _export_get_key(self):
        # Returns a unique functional key for self, built from a set of
        # fields defined in the _export_keys method.
        # This key is a tuple of (field_name, field_value) tuples.
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

    def _export_prepare(self, exported, force_key):
        # exported is a dict which hold a log of what has already been exported
        # It uses the class __name__ as a first key to get to a set of the
        # functional keys of already exported records.
        if self.__name__ not in exported:
            exported[self.__name__] = set()
        if force_key is None:
            my_key = self._export_get_key()
        else:
            if len(force_key) == 3 and isinstance(force_key[2], int):
                # We are in the case of a O2M forced key.
                my_key = force_key
            else:
                my_key = force_key[1]
        exported[self.__name__].add(my_key)
        return my_key

    @classmethod
    def _export_find_instance(cls, instance_key):
        # Tries to find an instance from its key
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

    @classmethod
    def _export_must_export_field(cls, field_name, field):
        if field_name in cls._export_skips():
            return False
        if isinstance(field, tryton_fields.Function) and not isinstance(
                field, tryton_fields.Property):
            return False
        return True

    @classmethod
    def _export_check_value_exportable(cls, field_name, field, field_value):
        result = True
        if isinstance(field, (tryton_fields.Many2One, tryton_fields.One2Many)):
            if hasattr(Pool().get(field.model_name), 'export_json'):
                result = True
            else:
                if field_name in cls._export_force_recreate():
                    result = True
                else:
                    result = False
        elif isinstance(field, (
                tryton_fields.One2One, tryton_fields.Many2Many)):
            RelationModel = Pool().get(field.relation_name)
            target_field = RelationModel._fields[field.target]
            if not hasattr(
                    Pool().get(target_field.model_name), 'export_json'):
                result = False
            else:
                result = True
        elif isinstance(field, tryton_fields.Reference):
            if isinstance(field_value, basestring):
                good_model = Pool().get(field_value.split(',')[0])
            else:
                good_model = field_value
            if hasattr(good_model, 'export_json'):
                result = True
            else:
                result = False
        if not result:
            raise NotExportImport('%s => %s' % (cls.__name__, field_name))

    @classmethod
    def _export_single_link(
            cls, exported, export_result, field_name, field, field_value,
            from_field, force_key, values):
        if isinstance(field, tryton_fields.Reference):
            f = lambda x: (field_value.__name__, x)
        else:
            f = lambda x: x
        if field_name == from_field and force_key:
            values[field_name] = f(force_key[0])
            return
        field_key = field_value._export_get_key()
        if field_key in exported.get(field_value.__name__, set()) or \
                field_name in cls._export_light():
            values[field_name] = f(field_key)
        else:
            values[field_name] = f(field_key)
            field_value._export_json(exported, export_result)

    @classmethod
    def _export_multiple_link(
            cls, exported, export_result, field_name, field, field_value,
            my_key, values):
        field_export_value = []
        if field_name in cls._export_force_recreate():
            idx = 1
            for elem in field_value:
                try:
                    elem_key = (my_key, elem._export_get_key())
                except NotExportImport:
                    elem_key = (my_key, field_name, idx)
                field_export_value.append(elem._export_json(
                    exported, export_result, field.field, elem_key))
                idx += 1
        else:
            for elem in field_value:
                elem_key = elem._export_get_key()
                if elem_key in exported.get(elem.__name__, {}) or \
                        field_name in cls._export_light():
                    field_export_value.append(elem_key)
                else:
                    field_export_value.append(elem_key)
                    elem._export_json(exported, export_result)
        values[field_name] = field_export_value

    def _export_json(
            self, exported, export_result, from_field=None, force_key=None):
        singleton = isinstance(self, ModelSingleton)
        if not (self.id > 0) and singleton:
            instance = self.get_singleton()
            return instance._export_json(exported, export_result, from_field,
                force_key)
        try:
            log_name = self.get_rec_name(None)
        except TypeError:
            log_name = self.get_rec_name([self], None)[self.id]
        if force_key is None and from_field is None:
            logging.getLogger('export_import').debug(
                'Trying to export %s' % log_name)
        my_key = self._export_prepare(exported, force_key)
        values = {
            '__name__': self.__name__,
            '_export_key': my_key}
        # Use "sorted" on fields keys to be sure of the order
        for field_name in sorted(self._fields.iterkeys()):
            field = self._fields[field_name]
            if not self._export_must_export_field(field_name, field):
                continue
            if hasattr(self, '_export_override_%s' % field_name):
                values[field_name] = getattr(
                    self, '_export_override_%s' % field_name)(exported,
                        export_result, my_key)
                continue
            field_value = getattr(self, field_name)
            if field_value is None:
                continue
            self._export_check_value_exportable(field_name, field, field_value)
            logging.getLogger('export_import').debug(
                'Exporting field %s.%s' % (self.__name__, field_name))
            if isinstance(field, tryton_fields.Property):
                field = field._field
            if isinstance(field, (
                    tryton_fields.Many2One, tryton_fields.One2One,
                    tryton_fields.Reference)):
                self._export_single_link(
                    exported, export_result, field_name, field, field_value,
                    from_field, force_key, values)
            elif (isinstance(field, tryton_fields.Many2Many) or
                    isinstance(field, tryton_fields.One2Many)):
                self._export_multiple_link(
                    exported, export_result, field_name, field, field_value,
                    my_key, values)
            else:
                values[field_name] = getattr(self, field_name)
        if force_key is None and from_field is None:
            if not singleton:
                export_result.append(values)
            logging.getLogger('export_import').debug(
                'Successfully exported %s' % log_name)
        return values

    def _export_filename(self):
        if (hasattr(self, 'code') and self.code):
            return self.code
        return self.get_rec_name(None)

    def _export_filename_prefix(self):
        return '[%s][%s]' % (datetime.date.today().isoformat(), self.__name__)

    def export_json(self):
        filename = '%s%s.json' % (
            self._export_filename_prefix(), self._export_filename())
        exported = {}
        result = []
        self._export_json(exported, result)
        instances = {}
        for value in result:
            if not value['__name__'] in instances:
                instances[value['__name__']] = []
            instances[value['__name__']].append(value['_export_key'])
        export_log = ''
        for k, v in instances.iteritems():
            export_log += '<b>%s</b>\n' % k
            for elem in v:
                export_log += '    %s\n' % str(elem)
        return filename, result, export_log

    @classmethod
    def _import_get_working_instance(cls, key):
        good_instance = cls._export_find_instance(key)
        if good_instance is None:
            good_instance = cls()
        good_instance._prepare_for_import()
        return good_instance

    @classmethod
    def _import_single_link(
            cls, instance, field_name, field, field_value, created, relink,
            target_model, to_relink):
        check_req = False
        if isinstance(field_value, tuple):
            if (target_model.__name__ in created and
                    field_value in created[target_model.__name__]):
                target_value = created[
                    target_model.__name__][field_value]
                if hasattr(target_value, 'id') and target_value.id:
                    setattr(instance, field_name, created[
                        target_model.__name__][field_value])
                else:
                    check_req = True
            else:
                good_value = target_model._export_find_instance(
                    field_value)
                if good_value:
                    setattr(instance, field_name, good_value)
                else:
                    check_req = True
        else:
            setattr(
                instance, field_name, target_model._import_json(
                    field_value, created=created, relink=relink))
        if not check_req:
            return True
        if (not('required' in field.states) and not
                field.required):
            to_relink.insert(0,
                (field_name, (target_model.__name__, field_value)))
            return True
        if field.required:
            to_relink.append(
                (field_name, (target_model.__name__, field_value)))
            return False
        to_relink.insert(0,
            (field_name, (target_model.__name__, field_value)))
        return not utils.pyson_result(field.states['required'], instance, True)

    @classmethod
    def _import_one2many(
            cls, instance, field_name, field, field_value, created, relink,
            to_relink):
        existing_values = getattr(instance, field_name) \
            if hasattr(instance, field_name) else None
        TargetModel = Pool().get(field.model_name)
        if not instance.id:
            pass
        elif (field_name in cls._export_force_recreate()):
            TargetModel.delete([elem for elem in existing_values])
        # else:
            # found = []
            # for elem in field_value:
                # if isinstance(elem, tuple):
                    # found.append(elem)
                # else:
                    # found.append(elem['_export_key'])
            # print found
            # print str([z for z in found])
            # TargetModel.delete(TargetModel.search([
                    # (field.field, '=', instance.id)] + [
                        # [['OR'] + [(k, '!=', v) for k, v in z]]
                        # for z in found]))
        for elem in field_value:
            if isinstance(elem, tuple):
                continue
            TargetModel._import_json(elem, created=created, relink=relink)

    @classmethod
    def _import_many2many(
            cls, instance, field_name, field, field_value, created, relink,
            to_relink):
        if (hasattr(instance, 'id') and instance.id):
            # For now, just recreate the links
            RelationModel = Pool().get(field.relation_name)
            RelationModel.delete(RelationModel.search([
                (field.origin, '=', instance.id)]))
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
                    elem, created=created, relink=relink))
        setattr(instance, field_name, good_values)
        if relinks:
            to_relink.append(
                (field_name, (TargetModel.__name__, relinks)))

    @classmethod
    def _import_finalize(cls, key, instance, save, created, relink, to_relink):
        if not cls.__name__ in created:
            created[cls.__name__] = {}
        if key in created[cls.__name__]:
            raise NotExportImport('Already existing key (%s) for class %s' % (
                key, cls.__name__))
        created[cls.__name__][key] = instance
        if save:
            try:
                instance.save()
            except:
                # print '\n'.join([str(x) for x in relink])
                # print utils.format_data(created)
                # print utils.format_data(instance)
                for x in traceback.format_exception(*sys.exc_info()):
                    logging.getLogger('export_import').debug(str(x))
                raise

        if to_relink:
            relink.append(((cls.__name__, key), to_relink))

    @classmethod
    def _import_json(
            cls, values, created, relink, force_recreate=False):
        assert values['__name__'] == cls.__name__
        save = True
        to_relink = []
        my_key = values['_export_key']
        logging.getLogger('export_import').debug(
            'Importing %s %s' % (cls.__name__, my_key))
        good_instance = cls._import_get_working_instance(my_key)
        for field_name in sorted(cls._fields.iterkeys()):
            if not field_name in values:
                continue
            field = cls._fields[field_name]
            field_value = values[field_name]
            logging.getLogger('export_import').debug(
                'Importing field %s : %s' % (field_name, field_value))
            if hasattr(cls, '_import_override_%s' % field_name):
                values[field_name] = getattr(
                    cls, '_import_override_%s' % field_name)(my_key,
                        good_instance, field_value, values, created, relink)
                continue
            if isinstance(field, tryton_fields.Property):
                field = field._field
            if isinstance(field, (
                    tryton_fields.Many2One, tryton_fields.One2One)):
                TargetModel = Pool().get(field.model_name)
                save = cls._import_single_link(
                    good_instance, field_name, field, field_value, created,
                    relink, TargetModel, to_relink) and save
            elif isinstance(field, tryton_fields.Reference):
                if isinstance(field_value, tuple):
                    field_model, field_value = field_value
                    TargetModel = Pool().get(field_model)
                else:
                    TargetModel = Pool().get(field_value['__name__'])
                save = cls._import_single_link(
                    good_instance, field_name, field, field_value, created,
                    relink, TargetModel, to_relink) and save
            elif isinstance(field, tryton_fields.One2Many):
                cls._import_one2many(
                    good_instance, field_name, field, field_value, created,
                    relink, to_relink)
            elif isinstance(field, tryton_fields.Many2Many):
                cls._import_many2many(
                    good_instance, field_name, field, field_value, created,
                    relink, to_relink)
            else:
                setattr(good_instance, field_name, field_value)
        cls._import_finalize(
            my_key, good_instance, save, created, relink, to_relink)
        return good_instance

    @classmethod
    def _import_relink(cls, created, relink):
        # Useful for debugging
        # print utils.format_data(created)
        # print '\n'.join([str(x) for x in relink])
        counter = 0
        while len(relink) > 0:
            counter += 1
            cur_errs = []
            to_del = []
            idx = 0
            for key, value in relink:
                logging.getLogger('export_import').debug(
                    'Relinking %s' % str(key))
                working_instance = created[key[0]][key[1]]
                # print utils.format_data(working_instance)
                all_done = True
                clean_keys = []
                relink_idx = -1
                for field_name, field_value in value:
                    relink_idx += 1
                    if isinstance(field_value[1], list):
                        to_append = []
                        for elem in field_value[1]:
                            elem_instance = created[field_value[0]][elem]
                            if (hasattr(elem_instance, 'id') and
                                    elem_instance.id):
                                to_append.append(elem_instance)
                            else:
                                all_done = False
                                continue
                        if len(to_append) == len(field_value[1]):
                            existing = list(getattr(
                                working_instance, field_name))
                            existing += to_append
                            setattr(working_instance, field_name, existing)
                    else:
                        the_value = created[field_value[0]][field_value[1]]
                        if not (hasattr(the_value, 'id') and the_value.id):
                            all_done = False
                            continue
                        setattr(working_instance, field_name, the_value)
                        clean_keys.append(relink_idx)
                for k in sorted(clean_keys, reverse=True):
                    value.pop(k)
                try:
                    if working_instance.id or not value:
                        working_instance.save()
                        if all_done:
                            to_del.append(idx)
                    else:
                        first_remaining = value[0]
                        field = working_instance._fields[first_remaining[0]]
                        req = False
                        if field.required:
                            req = True
                        elif 'required' in field.states:
                            req = utils.pyson_result(field.states['required'],
                                working_instance, True)
                        if not req:
                            working_instance.save()
                            if all_done:
                                to_del.append(idx)
                    idx += 1
                except UserError, e:
                    cur_errs.append(e.args)
                    idx += 1
                    continue
                except Exception:
                    logging.getLogger('export_import').debug(
                        'Error trying to save \n%s' % utils.format_data(
                            working_instance))
                    for x in traceback.format_exception(*sys.exc_info()):
                        logging.getLogger('export_import').debug(str(x))
                    raise
            for k in sorted(to_del, reverse=True):
                relink.pop(k)
            if len(to_del) == 0:
                # Useful for debugging
                # print '#' * 80
                # print 'CREATED DATA'
                # print utils.format_data(created)
                # print '#' * 80
                # print 'RELINKS'
                # print '\n'.join([str(x) for x in relink])
                # print '#' * 80
                print 'User Errors'
                print '\n'.join((utils.format_data(err) for err in cur_errs))
                raise NotExportImport('Infinite loop detected in import')
        logging.getLogger('export_import').debug('FINISHED IMPORT')
        logging.getLogger('export_import').debug(counter)

    @classmethod
    def _import_complete(cls, created):
        for k, v in created.iteritems():
            CurModel = Pool().get(k)
            CurModel._post_import([elem for elem in v.itervalues()])

    @classmethod
    def import_json(cls, values):
        with Transaction().set_user(0), Transaction().set_context(
                company=None), Transaction().set_context(__importing__=True):
            if isinstance(values, basestring):
                values = json.loads(values, object_hook=object_hook)
                values = map(utils.recursive_list_tuple_convert, values)
            created = {}
            relink = []
            main_instances = []
            for value in values:
                logging.getLogger('export_import').debug(
                    'First pass for %s %s' % (
                        value['__name__'], value['_export_key']))
                TargetModel = Pool().get(value['__name__'])
                main_instances.append(
                    TargetModel._import_json(value, created, relink))
            cls._import_relink(created, relink)
            cls._import_complete(created)
        for instance in main_instances:
            try:
                log_name = instance.get_rec_name(None)
            except TypeError:
                log_name = instance.get_rec_name([instance], None)[instance.id]
            logging.getLogger('export_import').debug(
                'Successfully imported %s' % log_name)
        return created


class FileSelector(ModelView):
    'File Selector'

    __name__ = 'coop_utils.file_selector'

    selected_file = fields.Binary('Import File', filename='name')
    name = fields.Char('Filename')
    file_content = fields.Text(
        'File Content', on_change_with=['selected_file'])

    def on_change_with_file_content(self):
        if not (hasattr(self, 'selected_file') and self.selected_file):
            return ''
        else:
            file_buffer = self.selected_file
            values = str(file_buffer)
            values = json.loads(values, object_hook=object_hook)
            instances = {}
            for value in values:
                if not value['__name__'] in instances:
                    instances[value['__name__']] = []
                instances[value['__name__']].append(value['_export_key'])
            result = ''
            for k, v in instances.iteritems():
                result += '<b>%s</b>\n' % k
                for elem in v:
                    result += '    %s\n' % elem
            return result


class ImportWizard(Wizard):
    'Import Wizard'

    __name__ = 'coop_utils.import_wizard'

    start_state = 'file_selector'
    file_selector = StateView(
        'coop_utils.file_selector',
        'coop_utils.file_selector_form',
        [
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


class ExportInstance(ExportImportMixin, ModelSQL, ModelView):
    'Export Instance'

    __name__ = 'coop_utils.export_instance'

    to_export = fields.Reference('To export', 'get_all_exportable_models',
        required=True)
    package = fields.Many2One('coop_utils.export_package', 'Package',
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

    __name__ = 'coop_utils.export_package'
    _rec_name = 'package_name'

    code = fields.Char('Code')
    package_name = fields.Char('Package Name', required=True)
    instances_to_export = fields.One2Many('coop_utils.export_instance',
        'package', 'Instances to export')
    model = fields.Function(
        fields.Selection('get_possible_models_to_export', 'Model'),
        'getter_void', setter='setter_void')

    @classmethod
    def __setup__(cls):
        super(ExportPackage, cls).__setup__()
        cls.__rpc__.update({'get_possible_models_to_export': RPC()})

    @classmethod
    def get_possible_models_to_export(cls):
        return [('', '')]

    def _on_change(self, name):
        existing = [x.to_export for x in self.instances_to_export]
        offered = [x for x in getattr(self, name) if not x in existing]
        res = {'instances_to_export': {'add': [{
                        'to_export': '%s,%s' % (x.__name__, x.id)}
                    for x in offered]}}
        res['model'] = ''
        return res

    def getter_void(self, name):
        return None

    @classmethod
    def setter_void(cls, instances, name, value):
        pass


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


def add_export_to_model(models, module_name):
    def class_generator(model_name, keys):
        class GenericClass(ExportImportMixin):
            __metaclass__ = PoolMeta
            __name__ = model_name

            @classmethod
            def _export_keys(cls):
                return set(keys)

            @classmethod
            def __setup__(cls):
                super(GenericClass, cls).__setup__()

            @classmethod
            def __register__(cls, module_name):
                super(GenericClass, cls).__register__(module_name)

        GenericClass.__doc__ = model_name
        return GenericClass

    classes = []
    for model, keys in models:
        classes.append(class_generator(model, keys))
    Pool.register(*classes, module=module_name, type_='model')


def clean_domain_for_import(domain, detect_key=None):
    if not detect_key:
        return [(If(~Eval('context', {}).get('__importing__', 0), domain, []))]
    final_domain = []
    for elem in domain:
        # TODO : Improve detection
        tmp_domain = PYSONEncoder().encode([elem])
        if detect_key in str(tmp_domain):
            final_domain.append(
                (If(~Eval('context', {}).get('__importing__', 0), elem, ())))
        else:
            final_domain.append(elem)
    return final_domain


class UIMenu():
    "UI menu"
    __name__ = 'ir.ui.menu'
    __metaclass__ = PoolMeta

    def get_rec_name(self, name):
        return self.name
