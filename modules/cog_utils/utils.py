import os
import datetime
import time
import copy
import string
import random
from collections import defaultdict

from trytond.pool import Pool
from trytond.model import Model
from trytond.transaction import Transaction
from trytond.model import fields


# Needed for Pyson evaluation
from trytond.pyson import PYSONDecoder, PYSONEncoder, CONTEXT, Eval, Or, And
from trytond.tools import safe_eval
from trytond.model.modelstorage import EvalEnvironment


__all__ = []


def get_module_name(cls):
    return cls.__name__.split('.')[0]


def to_list(data):
    if type(data) == list:
        return data
    elif type(data) == str:
        return [data]
    else:
        return [data]


def save_all(to_save):
    create_indexes = defaultdict(list)
    actions = defaultdict(lambda: defaultdict(list))
    for idx, elem in enumerate(to_save):
        save_values = elem._save_values
        if elem.id and save_values:
            actions[elem.__class__]['write'] += [[elem], save_values]
        elif not elem.id:
            create_indexes[elem.__class__].append(idx)
            actions[elem.__class__]['create'].append(save_values)
        else:
            raise Exception('save_all cannot save %r' % elem)
    for klass, action_dict in actions.iteritems():
        for action_name, values in action_dict.iteritems():
            if not values:
                continue
            if action_name == 'write':
                klass.write(*values)
            elif action_name == 'create':
                ids = klass.create(values)
                for id, idx in zip(ids, create_indexes[klass]):
                    instance = to_save[idx]
                    instance._values = None
                    instance.id = id
                    instance._ids.append(id)


def add_results(results):
    # This function can be used to concatenate simple return types, of the
    # form (result, [errors]).
    # It supposes that the result's type supports the += operator
    res = [None, []]
    for cur_res in results:
        if cur_res == (None, []):
            continue
        elif cur_res[0] is None:
            res[1] += cur_res[1]
        elif res[0] is None:
            res[0] = cur_res[0]
            res[1] += cur_res[1]
        else:
            res[0] += cur_res[0]
            res[1] += cur_res[1]
    return tuple(res)


def get_data_from_dict(data, the_dict):
    # This is used to parse a given dict for a set of data, and returns a dict
    # and a list of errors in the case it could not find one or more of the
    # specified data keys in the dict.
    res = ({}, [])
    for elem in data:
        if elem in the_dict:
            res[0][elem] = the_dict[elem]
        else:
            res[1] += '%s data not found' % elem
    return res


def convert_ref_to_obj(ref):
    model, id = ref.split(',')
    return Pool().get(model)(int(id))


def limit_dates(dates, start=None, end=None):
    res = set([x for x in dates
            if (not start or x >= start) and (not end or x < end)])
    if end:
        res.add(end)
    return sorted(res)


def to_date(string, format='ymd'):
    elems = [int(value) for value in string.split('-')]
    return datetime.date(elems[0], elems[1], elems[2])


def get_field_size(the_instance, val_name):
    field = getattr(the_instance.__class__, val_name)
    if field and hasattr(field, 'size'):
        return field.size


def tuple_index(value, the_tuple, key_index=0):
    '''
    Retrieve the index of the value in the tuple, comparing the
    value with the key_index value of the tuple'''
    return [y[key_index] for y in list(the_tuple)].index(value)


def get_module_path(module_name):
    module_path = os.path.abspath(os.path.join(
            os.path.normpath(__file__), '..', '..', module_name))
    if os.path.isdir(module_path):
        return module_path


def today():
    return Pool().get('ir.date').today()


def is_effective_at_date(instance, at_date=None, start_var_name='start_date',
        end_var_name='end_date'):
    if not at_date:
        at_date = today()
    start_date = getattr(instance, start_var_name, None) or datetime.date.min
    end_date = getattr(instance, end_var_name, None) or datetime.date.max
    return start_date <= at_date <= end_date


def get_good_versions_at_date(instance, var_name, at_date=None,
        start_var_name='start_date', end_var_name='end_date'):
    '''This method looks for the elements in the list which are effective at
    the date. By default, it will check that the at_date is between the start
    date and the end_date, otherwise it will check if there is already a
    specific method on the object'''

    if not at_date:
        at_date = today()
    get_good_versions_at_date = getattr(instance,
        'get_good_versions_at_date', None)
    if get_good_versions_at_date:
        return get_good_versions_at_date(var_name, at_date)
    res = set()
    for elem in reversed(getattr(instance, var_name, [])):
        if is_effective_at_date(elem, at_date, start_var_name, end_var_name):
            res.add(elem)
    return list(set(res))


def get_good_version_at_date(instance, var_name, at_date=None):
    res = get_good_versions_at_date(instance, var_name, at_date)
    if len(res) == 1:
        return res[0]


def find_date(list_to_filter, date):
    for elem in list_to_filter:
        if (elem.start_date or datetime.date.min) < date < (elem.end_date or
                datetime.date.max):
            return elem
    return None


def get_those_objects(model_name, domain, limit=None):
    the_model = Pool().get(model_name)
    return the_model.search(domain, limit=limit)


def get_this_object(model_name, domain):
    res, = get_those_objects(model_name, domain)
    return res


def delete_reference_backref(objs, target_model, target_field):
    the_model = Pool().get(target_model)
    to_delete = the_model.search([(
                target_field, 'in', [
                    '%s,%s' % (obj.__name__, obj.id)
                    for obj in objs])])
    the_model.delete(to_delete)


def get_user_language():
    return get_this_object('ir.lang', [('code', '=', Transaction().language)])


def get_relation_model_name(from_class_or_instance, field_name):
    from_class = Pool().get(from_class_or_instance.__name__)
    field = getattr(from_class, field_name)
    if not hasattr(field, 'model_name') and hasattr(field, 'relation_name'):
        # M2M
        relation = Pool().get(field.relation_name)
        target_field = getattr(relation, field.origin)
        res = target_field.model_name
    else:
        res = field.model_name
    return res


def create_inst_with_default_val(from_class, field_name, action=None):
    res = {}
    model_name = get_relation_model_name(from_class, field_name)
    CurModel = Pool().get(model_name)
    fields_names = list(
        x for x in set(CurModel._fields.keys())
        if x not in [
            'id', 'create_uid', 'create_date', 'write_uid', 'write_date'])
    field = getattr(from_class, field_name)
    if not isinstance(field, fields.Many2One):
        if action:
            res = {action: [[0, CurModel.default_get(fields_names)]]}
        else:
            res = [CurModel.default_get(fields_names)]
    else:
        res = CurModel.default_get(fields_names)
    return res


def append_inexisting(cur_list, item):
    if item not in cur_list:
        cur_list.append(item)
    return cur_list


def extend_inexisting(into_list, elements):
    for item in elements:
        into_list = append_inexisting(into_list, item)
    return into_list


def set_default_dict(input_dict, data):
    for k in data.iterkeys():
        input_dict.setdefault(k, data[k])

    return input_dict


def format_data(data, prefix='', prefix_inc='    ', is_init=True):
    tmp = None
    if isinstance(data, list):
        tmp = [prefix + '[']
        for elem in data:
            tmp += format_data(elem, prefix + prefix_inc, is_init=False)
        tmp += [prefix + ']']
    elif isinstance(data, (set, tuple)):
        tmp = [prefix + '(']
        for elem in data:
            tmp += format_data(elem, prefix + prefix_inc, is_init=False)
        tmp += [prefix + ')']
    elif isinstance(data, dict):
        tmp = [prefix + '{']
        for k, v in data.iteritems():
            new_data = format_data(v, prefix + prefix_inc, is_init=False)
            tmp_res = [
                prefix + prefix_inc + k.__repr__() + ':' +
                new_data[0][len(prefix + prefix_inc) - 1:]]
            if len(new_data) > 1:
                tmp_res += new_data[1:]
            tmp += tmp_res
        tmp += [prefix + '}']
    elif isinstance(data, (str, unicode)):
        tmp = [prefix + '"' + data + '"']
    elif isinstance(data, Model) and is_init:
        tmp = [prefix + str(data) + ' : {']
        for k in data._fields:
            try:
                value = getattr(data, k)
            except:
                value = None
            if not value:
                continue
            new_data = format_data(value, prefix + prefix_inc, is_init=False)
            tmp_res = [
                prefix + prefix_inc + str(k) + ':' +
                new_data[0][len(prefix + prefix_inc) - 1:]]
            if len(new_data) > 1:
                tmp_res += new_data[1:]
            tmp += tmp_res
        tmp += [prefix + '}']
    elif data is None:
        tmp = [prefix + 'None']
    else:
        tmp = [prefix + data.__repr__()]

    if not tmp:
        return prefix

    if not is_init:
        return tmp

    return '\n'.join(tmp)


def pyson_result(pyson_expr, target, evaled=False):
    encoder = PYSONEncoder()
    if isinstance(pyson_expr, str):
        the_pyson = encoder.encode(safe_eval(pyson_expr, CONTEXT))
    elif isinstance(pyson_expr, dict):
        the_pyson = encoder.encode(safe_eval(str(pyson_expr), CONTEXT))
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
    res = encoder.encode(safe_eval(pyson_expr, CONTEXT))
    # TODO : Make this safer
    res = res.replace('true', 'True')
    res = res.replace('false', 'False')

    if not do_eval:
        return res
    else:
        return eval(res)


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


def convert_to_reference(target):
    return '%s,%s' % (target.__name__, target.id)


def get_versioning_domain(start_date, end_date=None, do_eval=True):
    if not end_date:
        end_date = start_date
    if do_eval:
        return [
            'OR',
            [
                ('end_date', '=', None),
                ('start_date', '<=', Eval(start_date))],
            [
                ('end_date', '!=', None),
                ('start_date', '<=', Eval(start_date)),
                ('end_date', '>=', Eval(end_date))]]
    else:
        return [
            'OR',
            [
                ('end_date', '=', None),
                ('start_date', '<=', start_date)],
            [
                ('end_date', '!=', None),
                ('start_date', '<=', start_date),
                ('end_date', '>=', end_date)]]


def update_states(cls, var_name, new_states, pyson_cond='Or'):
    '''
    This methods allows to update field states when overriding a field and you
    don't know what where the states defined at the higher level
    '''
    field_name = copy.copy(getattr(cls, var_name))
    if not field_name.states:
        field_name.states = {}
    for key, value in new_states.iteritems():
        if key not in field_name.states:
            field_name.states[key] = value
        elif field_name.states[key] != value:
            if pyson_cond == 'Or':
                field_name.states[key] = Or(field_name.states[key], value)
            elif pyson_cond == 'And':
                field_name.states[key] = And(field_name.states[key], value)
    setattr(cls, var_name, field_name)


def update_domain(cls, var_name, new_domain):
    '''
    This methods allows to update field domain when overriding a field and you
    don't know what where the domain defined at the higher level
    '''
    origin_field = copy.copy(getattr(cls, var_name))
    field_name = origin_field
    if isinstance(field_name, fields.Function):
        field_name = field_name._field
    if not field_name.domain:
        field_name.domain = []
    field_name.domain.extend(new_domain)
    try:
        field_name.domain = list(set(field_name.domain))
    except:
        pass
    setattr(cls, var_name, origin_field)


def update_depends(cls, var_name, new_depends):
    field_name = copy.copy(getattr(cls, var_name))
    if not field_name.depends:
        field_name.depends = []
    field_name.depends.extend(new_depends)
    setattr(cls, var_name, field_name)


def update_on_change(cls, var_name, new_on_change):
    field_name = copy.copy(getattr(cls, var_name))
    if not field_name.on_change:
        field_name.on_change = set()
    field_name.on_change |= set(new_on_change)
    setattr(cls, var_name, field_name)


def update_selection(cls, var_name, tuple_to_add=None, keys_to_remove=None):
    field_name = copy.copy(getattr(cls, var_name))
    if keys_to_remove:
        field_name.selection[:] = [(x[0], x[1]) for x in field_name.selection
            if not x[0] in keys_to_remove]
    if tuple_to_add:
        field_name.selection += tuple_to_add
    field_name.selection = list(set(field_name.selection))
    setattr(cls, var_name, field_name)


def get_team(good_user=None):
    if not good_user:
        User = Pool().get('res.user')
        good_user = User(Transaction().user)
    return good_user.team


def init_extra_data(extra_data_defs):
    res = {}
    if extra_data_defs:
        for extra_data_def in extra_data_defs:
            res[extra_data_def.name] = extra_data_def.get_default_value(None)
    return res


def init_extra_data_from_ids(ids):
    the_model = Pool().get('extra_data')
    res = {}
    for id in ids:
        elem = the_model(id)
        res[elem.name] = elem.get_default_value(None)
    return res


def recursive_list_tuple_convert(the_list):
    if isinstance(the_list, (list, tuple)):
        return tuple((recursive_list_tuple_convert(x) for x in the_list))
    elif isinstance(the_list, dict):
        return dict((
                (key, recursive_list_tuple_convert(value))
                for key, value in the_list.iteritems()))
    else:
        return the_list


def concat_res(res1, res2):
    res = list(res1)
    res[0] = res[0] and res2[0]
    res[1] += res2[1]
    return tuple(res)


def extract_object(instance, vars_name=None):
    res = {}
    for var_name in vars_name:
        extract_kind = 'full'
        if len(var_name) == 2:
            var_name, extract_kind = var_name
        if not getattr(instance, var_name):
            continue
        if isinstance(instance._fields[var_name],
                fields.Function):
            continue
        if isinstance(instance._fields[var_name],
                (fields.Many2Many, fields.One2Many)):
            res[var_name] = []
            for sub_inst in getattr(instance, var_name):
                res[var_name].append(sub_inst.extract_object(extract_kind))
        elif isinstance(instance._fields[var_name], fields.Many2One):
            try:
                res[var_name] = getattr(instance, var_name).extract_object(
                    extract_kind)
            except AttributeError:
                res[var_name] = getattr(getattr(instance, var_name), 'code')
        else:
            res[var_name] = getattr(instance, var_name)
    return res


def set_state_view_defaults(wizard, state_name):
    if not hasattr(wizard, state_name) or not getattr(wizard, state_name):
        return {}
    state = getattr(wizard, state_name)
    result = {}
    for field_name, _ in state._fields.iteritems():
        try:
            result[field_name] = getattr(state, field_name)
        except:
            pass
    return result


def id_generator(size=20, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


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
            getter_function = lambda x: x
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
