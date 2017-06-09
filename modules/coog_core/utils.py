# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import datetime
import time
import json
from filelock import FileLock

from sql import Column, Window, Null
from sql.conditionals import Coalesce
from sql.operators import Add
from sql.conditionals import Case
from sql.aggregate import Max

from trytond import backend
from trytond.pool import Pool
from trytond.model import fields as tryton_fields, Check
from trytond.protocols.jsonrpc import JSONDecoder
from trytond.transaction import Transaction
from trytond.tools import grouped_slice, cursor_dict
from trytond.config import config

# Needed for Pyson evaluation
from trytond.pyson import PYSONDecoder, PYSONEncoder, CONTEXT
from trytond.model.modelstorage import EvalEnvironment

from .model import fields

__all__ = []


class FileLocker:
    'Class that secure open file access'

    def __init__(self, path, *args, **kwargs):
        self.path = path
        self.lock_extension = kwargs.pop('lock_extension', 'lck')
        temporary_folder = config.get('TMP', 'folder')
        self.lock_path = kwargs.pop('lock_directory', temporary_folder)
        if not self.lock_path:
            self.lock_path = self.path
        else:
            self.lock_path = os.path.join(self.lock_path,
                os.path.basename(self.path))
        self.lock_path += ('.' + self.lock_extension)
        self.locker = FileLock(self.lock_path)
        self.args = args
        self.kwargs = kwargs
        self.file_obj = None

    def __enter__(self):
        self.locker.acquire(timeout=20)
        self.file_obj = open(self.path, *self.args, **self.kwargs)
        return self.file_obj

    def __exit__(self, type, value, traceback):
        self.file_obj.close()
        self.locker.release()

    def write(self, *args, **kwargs):
        return self.file_obj.write(*args, **kwargs)

    def close(self):
        return self.file_obj.close()


def multi_column_required(table, column_names):
    clause = reduce(Add,
        (Case((Column(table, x) == Null, 0), else_=1) for x in column_names))
    return Check(table, clause == 1)


def add_reference_index(klass, module_name):
    TableHandler = backend.get('TableHandler')
    table = TableHandler(klass, module_name)

    # Manually add index for references match
    ref_index = table.table_name + '_reference_index'
    if ref_index in table._indexes:
        return
    with Transaction().connection.cursor() as cursor:
        cursor.execute('CREATE INDEX "' + ref_index + '" ON "' +
            table.table_name + '" (textcat(\'' + klass.__name__ +
            ',\', CAST("id" AS VARCHAR)))')
        table._update_definitions(indexes=True)


def safe_open(filepath, *args, **kwargs):
    return FileLocker(filepath, *args, **kwargs)


def iterator_slice(objects, max):
        count = 0
        sliced = []
        for obj in objects:
            count += 1
            sliced.append(obj)
            if count % max == 0:
                count = 0
                yield sliced
                del sliced[:]
        if sliced:
            yield sliced
            del sliced[:]


def remove_lockfile(filepath, lock_extension='lck', silent=True):
    lock_filepath = filepath + '.' + lock_extension
    try:
        os.remove(lock_filepath)
    except OSError:
        if silent:
            pass
        else:
            raise


def get_trytond_modules():
    Module = Pool().get('ir.module')
    modules = Module.search([])
    coog_core = Module.search([('name', '=', 'coog_core')])[0]

    def is_coog_module(module):
        if module.name.endswith('cog_translation') or \
                module.name == 'coog_core' or coog_core in module.parents:
            return True
        return any([is_coog_module(x) for x in module.parents])

    trytond_modules = []
    for module in modules:
        if not is_coog_module(module):
            trytond_modules.append(module.name)
    return trytond_modules


def models_get():
    return Pool().get('ir.property').models_get()


def is_module_installed(module_name):
    return Pool().get('ir.module').is_module_installed(module_name)


def get_field_size(the_instance, val_name):
    field = getattr(the_instance.__class__, val_name)
    if field and hasattr(field, 'size'):
        return field.size


def get_module_path(module_name):
    module_path = os.path.abspath(os.path.join(
            os.path.normpath(__file__), '..', '..', module_name))
    if os.path.isdir(module_path):
        return module_path


def today():
    return Pool().get('ir.date').today()


def now():
    return datetime.datetime.combine(today(), datetime.datetime.now().time())


def is_effective_at_date(instance, at_date=None, start_var_name='start_date',
        end_var_name='end_date'):
    if not at_date:
        at_date = today()
    start_date = getattr(instance, start_var_name, None) or datetime.date.min
    end_date = getattr(instance, end_var_name, None) or datetime.date.max
    return start_date <= at_date <= end_date


def filter_list_at_date(list_, at_date=None, start_var_name='start_date',
        end_var_name='end_date'):
    if not at_date:
        at_date = today()
    return [x for x in list_ if is_effective_at_date(x, at_date,
        start_var_name, end_var_name)]


def get_good_versions_at_date(instance, var_name, at_date=None,
        start_var_name='start_date', end_var_name='end_date'):
    '''
    This method looks for the elements in the list which are effective at
    the date. By default, it will check that the at_date is between the start
    date and the end_date
    '''

    if not at_date:
        at_date = today()
    return filter_list_at_date(getattr(instance, var_name, []), at_date,
        start_var_name, end_var_name)


def get_good_version_at_date(instance, var_name, at_date=None,
        start_var_name='start_date', end_var_name='end_date'):
    if not at_date:
        at_date = today()
    versions = get_good_versions_at_date(instance, var_name, at_date,
        start_var_name, end_var_name)
    for version in sorted(versions, key=lambda v: getattr(v, start_var_name,
            None) or datetime.date.min, reverse=True):
        if ((getattr(version, start_var_name, None) or datetime.date.min)
                <= at_date):
            return version


def delete_reference_backref(objs, target_model, target_field):
    the_model = Pool().get(target_model)
    to_delete = the_model.search([(
                target_field, 'in', [
                    '%s,%s' % (obj.__name__, obj.id)
                    for obj in objs])])
    the_model.delete(to_delete)


def get_user_language():
    return Pool().get('ir.lang').get_from_code(Transaction().language)


def pyson_result(pyson_expr, target):
    encoder = PYSONEncoder()
    if isinstance(pyson_expr, basestring):
        the_pyson = encoder.encode(eval(pyson_expr, CONTEXT))
    else:
        the_pyson = encoder.encode(pyson_expr)
    if the_pyson is True:
        return True
    elif the_pyson is False:
        return False

    env = EvalEnvironment(target, target.__class__)
    env.update(Transaction().context)
    env['current_date'] = datetime.datetime.today()
    env['time'] = time
    env['context'] = Transaction().context
    env['active_id'] = target.id
    result = PYSONDecoder(env).decode(the_pyson)

    return result


def pyson_encode(pyson_expr, do_eval=False):
    encoder = PYSONEncoder()
    res = encoder.encode(eval(pyson_expr, CONTEXT))
    # TODO : Make this safer
    res = res.replace('true', 'True')
    res = res.replace('false', 'False')
    res = res.replace('null', 'None')

    if not do_eval:
        return res
    else:
        return eval(res)


def get_json_from_pyson(pyson):
    encoded = PYSONEncoder().encode(pyson)
    return ''.join([x if x != '"' else '&quot;' for x in encoded])


def get_domain_instances(record, field_name):
    field = record._fields[field_name]
    if isinstance(field, fields.Function):
        field = field._field
    if not isinstance(field, (fields.Many2One, fields.One2Many)):
        return []
    pyson_domain = PYSONEncoder().encode(field.domain)
    env = EvalEnvironment(record, record.__class__)
    env.update(Transaction().context)
    env['current_date'] = today()
    env['time'] = time
    env['context'] = Transaction().context
    env['active_id'] = record.id
    domain = PYSONDecoder(env).decode(pyson_domain)

    GoodModel = Pool().get(field.model_name)
    return GoodModel.search(domain)


def auto_complete_with_domain(record, field_name):
    instances = get_domain_instances(record, field_name)
    if len(instances) == 1:
        return instances[0].id


def convert_to_reference(target):
    return '%s,%s' % (target.__name__, target.id)


def init_extra_data(extra_data_defs):
    res = {}
    if extra_data_defs:
        for extra_data_def in extra_data_defs:
            res[extra_data_def.name] = extra_data_def.get_default_value(None)
    return res


def get_value_at_date(the_list, at_date, date_field='date'):
    assert at_date
    assert date_field
    for elem in sorted(the_list, key=lambda x: getattr(x, date_field,
                None) or datetime.date.min, reverse=True):
        if (getattr(elem, date_field, None) or datetime.date.min) <= at_date:
            return elem
    return None


class ProxyListWithGetter(object):
    """
       A proxy class for lists which allows to use a custom method to get
       items from the list.

       This allows for instance to easily iterate on an attribute value of a
       list of objects :
           ProxyListWithGetter(parties, lambda x: x.name)

       will behave the same way that the list of names would.
   """

    def __init__(self, the_list, getter_function=None):
        if getter_function is None:
            def getter_function(x):
                return x

        self._the_list = the_list
        self._getter_function = getter_function

    def __getattr__(self, attrname):
        return getattr(self._the_list, attrname)

    def __getitem__(self, idx):
        return self._getter_function(self._the_list[idx])

    def __len__(self):
        # We must manually override __len__ because the len builtin does not
        # use getattr(__len__) for new style classes
        return len(self._the_list)


def get_history_instance(model_name, instance_id, at_date):
    with Transaction().set_context(_datetime=at_date):
        return Pool().get(model_name)(instance_id)


def apply_dict(instance, data_dict):
    pool = Pool()
    Model = pool.get(instance.__name__)
    for k, v in data_dict.iteritems():
        if k in ('create_date', 'create_uid', 'write_date', 'write_uid'):
            continue
        field = Model._fields[k]
        value = getattr(instance, k, None)
        if isinstance(field, tryton_fields.Many2One):
            if value and value.id == v:
                continue
            if v is None:
                if not hasattr(instance, k) or value != None:
                    setattr(instance, k, v)
            else:
                setattr(instance, k, pool.get(field.model_name)(v))
        elif isinstance(field, tryton_fields.Reference):
            model_name, value_id = v.split(',')
            if model_name == value.__name__ and value_id == value.id:
                continue
            setattr(instance, k, pool.get(model_name)(value_id))
        elif isinstance(field, (tryton_fields.One2Many,
                    tryton_fields.Many2Many)):
            to_keep = {x.id: x for x in (value or [])}
            prev_order = [x.id for x in (value or [])]
            new_values = []
            for action_data in v:
                if action_data[0] == 'delete':
                    for id_to_del in action_data[1]:
                        del to_keep[id_to_del]
                elif action_data[0] == 'write':
                    for id_to_update in action_data[1]:
                        apply_dict(to_keep[id_to_update], action_data[2])
                elif action_data[0] == 'add':
                    for id_to_add in action_data[1]:
                        if id_to_add not in to_keep:
                            new_values.append(pool.get(field.model_name)(
                                    id_to_add))
                elif action_data[0] == 'create':
                    for data_dict in action_data[1]:
                        new_instance = pool.get(field.model_name)()
                        apply_dict(new_instance, data_dict)
                        setattr(new_instance, field.field, instance)
                        new_values.append(new_instance)
                elif action_data[0] == 'remove' and isinstance(field,
                        tryton_fields.Many2Many):
                    for id_to_remove in action_data[1]:
                        del to_keep[id_to_remove]
                else:
                    raise Exception('unsupported operation')
            clean_list = [to_keep[x] for x in prev_order if x in to_keep]
            setattr(instance, k, clean_list + new_values)
        else:
            if v != value or not hasattr(instance, k):
                setattr(instance, k, v)


def chunker(seq, size):
    return (seq[pos:pos + size] for pos in xrange(0, len(seq), size))


def version_getter(instances, names, version_model, reverse_fname,
        at_date, date_field='start', field_map=None):
    '''
        Generic method for getting values for a versioned list at a given date.

        Required parameters :
         - instances : list of versioned objects to manage
         - names : list of fields to load.
         - version_model : the name of the version model
         - reverse_fname : the name of the reversed field for the version list
         - at_date : the date at which to look for the version

        Optional parameters :
         - date_field : the nams of the field to use for versions ordering
         - field_map : if set, will be used to convert name fields. Typical use
           case is :
                {'id': 'curret_version'},
           so that the 'current_version' field of the parent will receive the
           'id' field of the current version.
    '''
    assert version_model
    assert reverse_fname

    field_map = field_map or {}
    field_map = {x: field_map.get(x, x)
        for x in field_map.keys() + [x for x in names if x not in
            field_map.values()]}

    cursor = Transaction().connection.cursor()
    Target = Pool().get(version_model)
    target = Target.__table__()

    base_values = {x.id: None for x in instances}
    result, columns, to_convert = {}, [], set()
    for version_name, master_name in field_map.iteritems():
        columns.append(Column(target, version_name))
        if isinstance(Target._fields[version_name], tryton_fields.Dict):
            to_convert.add(version_name)
        result[master_name] = dict(base_values)

    start_col = Coalesce(Column(target, date_field),
        datetime.date.min).as_('start')
    parent_col = Column(target, reverse_fname)
    parent_window = Window([parent_col])
    max_col = Max(Coalesce(Column(target, date_field), datetime.date.min),
        window=parent_window).as_('max_start')
    columns += [start_col, max_col, parent_col]

    where_clause = Coalesce(Column(target, date_field),
        datetime.date.min) <= at_date

    for instance_slice in grouped_slice(instances):
        view = target.select(*columns, where=where_clause &
            parent_col.in_([x.id for x in instance_slice]))
        cursor.execute(*view.select(where=view.start == view.max_start))
        for value in cursor_dict(cursor):
            base_id = value[reverse_fname]
            for k, v in value.iteritems():
                if k == reverse_fname or k not in field_map:
                    continue
                if k in to_convert:
                    v = json.loads(v, object_hook=JSONDecoder())
                result[field_map[k]][base_id] = v
    return result


def clear_transaction_cache(model_name, ids):
    # Copied from ModelStorage::write
    for cache in Transaction().cache.itervalues():
        if model_name in cache:
            for id_ in ids:
                if id_ in cache[model_name]:
                    cache[model_name][id_].clear()


def get_view_complete_xml(model, view):
    return model.fields_view_get(view.id, view.rng_type)['arch']
