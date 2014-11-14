# -*- coding: utf-8 -*-
import traceback
import sys
import copy
import datetime
import collections
import logging
try:
    import simplejson as json
except ImportError:
    import json

from sql.operators import Concat

from trytond.protocols.jsonrpc import JSONEncoder, JSONDecoder
from trytond.model import Model, ModelSQL, ModelView, fields as tryton_fields
from trytond.model import ModelSingleton
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.pool import Pool, PoolMeta
from trytond.rpc import RPC
from trytond.exceptions import UserError
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, PYSONEncoder

import utils
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
        cls.__rpc__['export_ws_json_to_file'] = RPC(instantiate=0,
            readonly=True, result=lambda r: cls._export_format_result(r))
        cls.__rpc__['multiple_import_ws_json'] = RPC(readonly=False,
            result=lambda r: None)
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

    def _prepare_for_import(self):
        pass

    @classmethod
    def _post_import(cls, records):
        pass

    @classmethod
    def _export_format_result(cls, result):
        return (result[0], json.dumps(result[1], cls=JSONEncoder, indent=4,
                sort_keys=True, separators=(',', ': ')), result[2])

    @classmethod
    def _export_keys(cls):
        # Returns a set of fields which will be used to compute a unique
        # functional key for self.
        # field_name may use "." to chain if it is not ambiguous
        # TODO : Look for a field with 'UNIQUE' and 'required' attributes set
        # TODO : Cache this
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
        return set(('id', 'create_uid', 'write_uid', 'create_date',
                'write_date'))

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
        # It should be unique for each instance, so caching on the instance is
        # ok
        key = getattr(self, '_calculated_export_key', None)
        if key:
            return key
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
        self._calculated_export_key = tuple(result)
        return self._calculated_export_key

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
            raise NotExportImport('Multiple result found for key %s in class '
                '%s' % (instance_key, cls.__name__))
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
        elif isinstance(field, (tryton_fields.One2One,
                    tryton_fields.Many2Many)):
            RelationModel = Pool().get(field.relation_name)
            target_field = RelationModel._fields[field.target]
            if not hasattr(Pool().get(target_field.model_name), 'export_json'):
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
    def _export_single_link(cls, exported, export_result, field_name, field,
            field_value, from_field, force_key, values):
        if field_value is None:
            values[field_name] = None
            return
        if isinstance(field, tryton_fields.Reference):
            f = lambda x: (field_value.__name__, x)
        else:
            f = lambda x: x
        if field_name == from_field and force_key:
            values[field_name] = f(force_key[0])
            return
        field_key = field_value._export_get_key()
        if (field_key in exported.get(field_value.__name__, set()) or
                field_name in cls._export_light()):
            values[field_name] = f(field_key)
        else:
            values[field_name] = f(field_key)
            field_value._export_json(exported, export_result)

    @classmethod
    def _export_multiple_link(cls, exported, export_result, field_name, field,
            field_value, my_key, values):
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
                if (elem_key in exported.get(elem.__name__, {}) or
                        field_name in cls._export_light()):
                    field_export_value.append(elem_key)
                else:
                    field_export_value.append(elem_key)
                    elem._export_json(exported, export_result)
        values[field_name] = field_export_value

    def _export_json(self, exported, export_result, from_field=None,
            force_key=None):
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
            logging.getLogger('export_import').debug('Trying to export %s' %
                log_name)
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
                values[field_name] = getattr(self, '_export_override_%s' %
                    field_name)(exported, export_result, my_key)
                continue
            field_value = getattr(self, field_name)
            self._export_check_value_exportable(field_name, field, field_value)
            logging.getLogger('export_import').debug('Exporting field %s.%s' %
                (self.__name__, field_name))
            if isinstance(field, tryton_fields.Property):
                field = field._field
            if isinstance(field, (tryton_fields.Many2One,
                        tryton_fields.One2One, tryton_fields.Reference)):
                self._export_single_link(exported, export_result, field_name,
                    field, field_value, from_field, force_key, values)
            elif isinstance(field, (tryton_fields.Many2Many,
                    tryton_fields.One2Many)):
                self._export_multiple_link(exported, export_result, field_name,
                    field, field_value, my_key, values)
            else:
                values[field_name] = getattr(self, field_name)
        if force_key is None and from_field is None:
            if not singleton:
                export_result.append(values)
            logging.getLogger('export_import').debug('Successfully exported %s'
                % log_name)
        return values

    def _export_filename(self):
        if (hasattr(self, 'code') and self.code):
            return self.code
        return self.get_rec_name(None)

    def _export_filename_prefix(self):
        return '[%s][%s]' % (datetime.date.today().isoformat(), self.__name__)

    def export_json(self):
        filename = '%s%s.json' % (self._export_filename_prefix(),
            self._export_filename())
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

    def export_ws_json_to_file(self):
        filename = '%s%s.json' % (self._export_filename_prefix(),
            self._export_filename())
        result = []
        self.export_ws_json(output=result)
        export_log = 'The following records will be exported:\n '
        instances = collections.defaultdict(list)
        for value in result:
            instances[value['__name__']].append(value['_func_key'])
        for k, v in instances.iteritems():
            export_log += '<b>%s</b>\n' % k
            for elem in v:
                export_log += '    %s\n' % elem
        return filename, result, export_log

    @classmethod
    def _import_get_working_instance(cls, key):
        good_instance = cls._export_find_instance(key)
        if good_instance is None:
            good_instance = cls()
        good_instance._prepare_for_import()
        return good_instance

    @classmethod
    def _import_single_link(cls, instance, field_name, field, field_value,
            created, relink, target_model, to_relink):
        check_req = False
        if field_value is None:
            setattr(instance, field_name, None)
        elif isinstance(field_value, tuple):
            if (target_model.__name__ in created and
                    field_value in created[target_model.__name__]):
                target_value = created[
                    target_model.__name__][field_value]
                if hasattr(target_value, 'id') and target_value.id:
                    setattr(instance, field_name,
                        created[target_model.__name__][field_value])
                else:
                    check_req = True
            else:
                good_value = target_model._export_find_instance(field_value)
                if good_value:
                    setattr(instance, field_name, good_value)
                else:
                    check_req = True
        else:
            setattr(instance, field_name, target_model._import_json(
                    field_value, created=created, relink=relink))
        if not check_req:
            return True
        to_relink[(target_model.__name__, field_value)]['from'][
            (cls.__name__, instance._export_get_key())] = instance
        if not('required' in field.states) and not field.required:
            to_relink[(cls.__name__, instance._export_get_key())][
                'opt'].update(
                {field_name: (target_model.__name__, field_value)})
            return True
        to_relink[(cls.__name__, instance._export_get_key())][
            'req'].update(
            {field_name: (target_model.__name__, field_value)})
        if field.required:
            return False
        return not utils.pyson_result(field.states['required'], instance, True)

    @classmethod
    def _import_one2many(cls, instance, field_name, field, field_value,
            created, relink, to_relink):
        existing_values = getattr(instance, field_name) if hasattr(instance,
            field_name) else None
        TargetModel = Pool().get(field.model_name)
        to_delete = []
        if not instance.id:
            pass
        elif field_name in cls._export_force_recreate():
            TargetModel.delete([elem for elem in existing_values])
        else:
            if TargetModel._export_keys():
                to_delete = dict([
                        (x._export_get_key(), x) for x in existing_values])
        for elem in field_value:
            if isinstance(elem, tuple):
                if elem in to_delete:
                    del to_delete[elem]
                continue
            TargetModel._import_json(elem, created=created, relink=relink)
        if to_delete:
            TargetModel.delete(list(to_delete.itervalues()))

    @classmethod
    def _import_many2many(cls, instance, field_name, field, field_value,
            created, relink, to_relink):
        RelationModel = Pool().get(field.relation_name)
        if (hasattr(instance, 'id') and instance.id):
            # For now, just recreate the links
            origin_field = RelationModel._fields[field.origin]
            if isinstance(origin_field, fields.Many2One):
                RelationModel.delete(RelationModel.search([
                            (field.origin, '=', instance.id)]))
            else:
                RelationModel.delete(RelationModel.search([
                            (field.origin, '=', '%s,%i' % (
                                    instance.__name__, instance.id))]))
        TargetModel = Pool().get(Pool().get(
            field.relation_name)._fields[field.target].model_name)
        good_values = []
        my_relink = to_relink[(cls.__name__, instance._export_get_key())]
        for elem in field_value:
            check_req = True
            if isinstance(elem, tuple):
                check_req = False
                if (TargetModel.__name__ in created and
                        elem in created[TargetModel.__name__]):
                    value = created[TargetModel.__name__][elem]
                    if getattr(value, 'id', False):
                        check_req = False
                        good_values.append(created[TargetModel.__name__][elem])
                else:
                    good_value = TargetModel._export_find_instance(elem)
                    if good_value:
                        good_values.append(good_value)
                        check_req = False
                    else:
                        check_req = True
            else:
                good_values.append(TargetModel._import_json(elem,
                        created=created, relink=relink))
                check_req = False
            if not check_req:
                continue
            to_relink[(TargetModel.__name__, elem)]['from'][
                (cls.__name__, instance._export_get_key())] = instance
            if not('required' in field.states) and not field.required:
                if field_name not in my_relink['opt']:
                    my_relink['opt'][field_name] = {}
                my_relink['opt'][field_name].update({
                            (TargetModel.__name__, elem): True})
            else:
                if field_name not in my_relink['req']:
                    my_relink['req'][field_name] = {}
                my_relink['req'][field_name].update({
                        (TargetModel.__name__, elem)})
        setattr(instance, field_name, good_values)

    @classmethod
    def _import_finalize(cls, key, instance, created, relink):
        if cls.__name__ not in created:
            created[cls.__name__] = {}
        if key in created[cls.__name__]:
            raise NotExportImport('Already existing key (%s) for class %s' % (
                key, cls.__name__))
        created[cls.__name__][key] = instance
        if not relink[(cls.__name__, key)]['req']:
            try:
                instance.save()
                cls._import_do_relink(key, instance, relink, created)
            except:
                logging.getLogger('export_import').debug(str(instance))
                for x in traceback.format_exception(*sys.exc_info()):
                    logging.getLogger('export_import').debug(str(x))
                raise

    @classmethod
    def _import_do_relink(cls, key, instance, relink, created):
        if not instance.id:
            return
        for src_key, source in relink[(cls.__name__, key)]['from'].iteritems():
            src_relink = relink[src_key]['opt']
            to_del = []
            for field_name, link_key in src_relink.iteritems():
                if (not isinstance(link_key, dict) and
                        link_key != (cls.__name__, key)):
                    continue
                if isinstance(link_key, dict):
                    if not (cls.__name__, key) in link_key:
                        continue
                    source_value = getattr(source, field_name)
                    if isinstance(source_value, tuple):
                        source_value = list(source_value)
                        setattr(source, field_name, source_value)
                    getattr(source, field_name).append(instance)
                    del link_key[(cls.__name__, key)]
                    if not link_key:
                        to_del.append(field_name)
                elif link_key == (cls.__name__, key):
                    setattr(source, field_name, instance)
                    to_del.append(field_name)
            for elem in to_del:
                del src_relink[elem]
            src_relink = relink[src_key]['req']
            to_del = []
            for field_name, link_key in src_relink.iteritems():
                if (not isinstance(link_key, dict) and
                        link_key != (cls.__name__, key)):
                    continue
                if isinstance(link_key, dict):
                    if not (cls.__name__, key) in link_key:
                        continue
                    getattr(source, field_name).append(instance)
                    del link_key[(cls.__name__, key)]
                    if not link_key:
                        to_del.append(field_name)
                elif link_key == (cls.__name__, key):
                    setattr(source, field_name, instance)
                    to_del.append(field_name)
            for elem in to_del:
                del src_relink[elem]
            if len(src_relink) == 0:
                source.save()
                source._import_do_relink(src_key[1], source, relink, created)

    @classmethod
    def _import_json(cls, values, created, relink, force_recreate=False):
        assert values['__name__'] == cls.__name__
        my_key = values['_export_key']
        logging.getLogger('export_import').debug('Importing %s %s' %
            (cls.__name__, my_key))
        good_instance = cls._import_get_working_instance(my_key)
        good_instance._calculated_export_key = my_key
        for field_name in sorted(cls._fields.iterkeys()):
            if field_name not in values:
                continue
            field = cls._fields[field_name]
            field_value = values[field_name]
            logging.getLogger('export_import').debug('Importing field %s : %s'
                % (field_name, field_value))
            if hasattr(cls, '_import_override_%s' % field_name):
                getattr(cls, '_import_override_%s' %
                    field_name)(my_key, good_instance, field_value, values,
                        created, relink, relink)
                continue
            if isinstance(field, tryton_fields.Property):
                field = field._field
            if isinstance(field, (tryton_fields.Many2One,
                        tryton_fields.One2One)):
                TargetModel = Pool().get(field.model_name)
                cls._import_single_link(good_instance, field_name,
                    field, field_value, created, relink, TargetModel,
                    relink)
            elif isinstance(field, tryton_fields.Reference):
                if isinstance(field_value, tuple):
                    field_model, field_value = field_value
                    TargetModel = Pool().get(field_model)
                else:
                    TargetModel = Pool().get(field_value['__name__'])
                cls._import_single_link(good_instance, field_name,
                    field, field_value, created, relink, TargetModel,
                    relink)
            elif isinstance(field, tryton_fields.One2Many):
                cls._import_one2many(good_instance, field_name, field,
                    field_value, created, relink, relink)
            elif isinstance(field, tryton_fields.Many2Many):
                cls._import_many2many(good_instance, field_name, field,
                    field_value, created, relink, relink)
            else:
                setattr(good_instance, field_name, field_value)
        cls._import_finalize(my_key, good_instance, created, relink)
        return good_instance

    @classmethod
    def _import_relink(cls, created, relink):
        counter = 0
        while len(relink) > 0:
            counter += 1
            cur_errs, to_del, idx = [], [], 0
            for key, value in relink:
                logging.getLogger('export_import').debug('Relinking %s : %s' %
                    (str(key), str(value)))
                working_instance = created[key[0]][key[1]]
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
                            existing = list(getattr(working_instance,
                                    field_name))
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
                except Exception, e:
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
                try:
                    print '\n'.join((utils.format_data(err)
                            for err in cur_errs))
                except:
                    print '\n'.join((str(err) for err in cur_errs))
                raise NotExportImport('Infinite loop detected in import')
        logging.getLogger('export_import').debug('FINISHED IMPORT')
        logging.getLogger('export_import').debug(counter)

    @classmethod
    def _import_complete(cls, created, relink):
        pool = Pool()
        for k, v in created.iteritems():
            CurModel = pool.get(k)
            CurModel._post_import([elem for elem in v.itervalues()])
        for k, v in relink.iteritems():
            assert not v['req']
            assert not v['opt']

    @classmethod
    def _import_must_validate(cls):
        return False

    @classmethod
    def _import_validate(cls, created):
        pool = Pool()
        for k, v in created.iteritems():
            CurModel = pool.get(k)
            if not CurModel._import_must_validate():
                continue
            logging.getLogger('export_import').debug('Validating %s models'
                % CurModel.__name__)
            CurModel._validate(v)

    @classmethod
    def import_json(cls, values):
        with Transaction().set_user(0), Transaction().set_context(
                __importing__=True, language='en_US'):
            if isinstance(values, basestring):
                values = json.loads(values, object_hook=JSONDecoder())
                values = map(utils.recursive_list_tuple_convert, values)
            created = {}
            relink = collections.defaultdict(
                lambda: {'from': {}, 'req': {}, 'opt': {}})
            main_instances = []
            for value in values:
                logging.getLogger('export_import').debug('First pass for %s %s'
                    % (value['__name__'], value['_export_key']))
                TargetModel = Pool().get(value['__name__'])
                main_instances.append(TargetModel._import_json(value, created,
                        relink))
            # cls._import_relink(created, relink)
        cls._import_complete(created, relink)
        for instance in main_instances:
            try:
                log_name = instance.get_rec_name(None)
            except TypeError:
                log_name = instance.get_rec_name([instance], None)[instance.id]
            logging.getLogger('export_import').debug('Successfully imported %s'
                % log_name)
        return created

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
    def _import_ws_json(cls, values, main_object=None):
        pool = Pool()
        new_values = {}
        lines = {}
        for field_name, value in values.iteritems():
            if field_name in ('__name__', '_func_key'):
                continue
            field = cls._fields[field_name]
            if isinstance(field, (tryton_fields.Many2One,
                        tryton_fields.Property, tryton_fields.One2One,
                        tryton_fields.Reference)):
                if value:
                    if isinstance(field, tryton_fields.Reference):
                        Target = pool.get(value['__name__'])
                    else:
                        Target = field.get_target()
                    target = Target.import_ws_json(value)
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
                            Target._import_ws_json(line,
                                Target(existing_line.id))))
                    del existing_lines[export_name]
                else:
                    if isinstance(field, tryton_fields.Many2Many):
                        # One2many to master object are not managed
                        if Target.search_for_export_import(line):
                            target = Target.import_ws_json(line)
                            to_add.append(target.id)
                            continue
                    obj_to_create = Target._import_ws_json(line, None)
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
            to_create = [('create', to_create)]
            for action in (to_write, to_create, to_delete, to_remove):
                if action:
                    new_values[field_name].extend(action)
            if to_add:
                new_values[field_name].append(('add', to_add))

        return new_values

    @classmethod
    def multiple_import_ws_json(cls, objects):
        pool = Pool()
        if isinstance(objects, basestring):
            objects = json.loads(objects, object_hook=JSONDecoder())
        for obj in objects:
            Target = pool.get(obj['__name__'])
            Target.import_ws_json(obj)

    @classmethod
    def import_ws_json(cls, values):
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
        new_values = cls._import_ws_json(values, record)

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
                self.export_ws_json(skip_fields, already_exported, output,
                    main_object)
            return {'_func_key': getattr(self, self._func_key),
                '__name__': self.__name__}

    def _export_ws_json_xxx2one(self, field_name, skip_fields=None,
            already_exported=None, output=None, main_object=None):
        target = getattr(self, field_name)
        if target is None:
            return None
        if not hasattr(target, 'export_ws_json'):
            raise NotExportImport('%s is not exportable' % target)
        if target:
            values = target.export_master(skip_fields, already_exported,
                output, main_object)
            if values is None:
                values = target.export_ws_json(skip_fields, already_exported,
                    output, main_object)
            return values

    def _export_ws_json_xxx2many(self, field_name, skip_fields=None,
            already_exported=None, output=None, main_object=None):
        if skip_fields is None:
            skip_fields = set()
        field = self._fields[field_name]
        if isinstance(field, tryton_fields.One2Many):
            skip_fields.add(field.field)
        Target = field.get_target()
        if Target is None:
            return None
        if not hasattr(Target, 'export_ws_json'):
            raise NotExportImport('%s is not exportable'
                % Target)
        targets = getattr(self, field_name) or []
        results = []
        for t in targets:
            values = t.export_master(skip_fields, already_exported, output,
                main_object)
            if not values:
                values = t.export_ws_json(skip_fields, already_exported,
                    output, main_object)
            if values:
                results.append(values)
        return results

    def export_ws_json(self, skip_fields=None, already_exported=None,
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
        elif not already_exported:
            already_exported = set([self])
        else:
            already_exported.add(self)

        light_exports = self._export_light()

        for field_name, field in self._fields.iteritems():
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
                values[field_name] = self._export_ws_json_xxx2one(
                    field_name, None, already_exported, output,
                    main_object)
            elif isinstance(field, (tryton_fields.One2Many,
                        tryton_fields.Many2Many)):
                values[field_name] = self._export_ws_json_xxx2many(
                    field_name, None, already_exported, output,
                    main_object)
            else:
                values[field_name] = getattr(self, field_name)
        if self.is_master_object() or main_object == self:
            output.append(values)
        return values


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
                instances[value['__name__']].append(value['_export_key'])
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
        ExportImportMixin.import_json(values)
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
