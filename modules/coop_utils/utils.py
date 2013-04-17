import ConfigParser
import os
import datetime
import time
import copy
from dateutil.relativedelta import relativedelta

from trytond.pool import Pool
from trytond.model import Model
from trytond.transaction import Transaction
from trytond.model import fields


# Needed for Pyson evaluation
from trytond.pyson import PYSONDecoder, PYSONEncoder, CONTEXT, Eval, Or, And
from trytond.tools import safe_eval
from trytond.model.modelstorage import EvalEnvironment


__all__ = []


def get_child_models(from_class):
    if isinstance(from_class, str):
        try:
            the_class = Pool().get(from_class)
        except KeyError:
            raise
        cur_models = [model_name
                      for model_name, model in Pool().iterobject()
                      if issubclass(model, the_class)]
        models = map(lambda x: Pool().get(x), cur_models)
        return models
    elif isinstance(from_class, type):
        res = []
        names = [elem for elem, _ in Pool().iterobject()]
        for elem in from_class.__subclasses__():
            if isinstance(elem, type) and elem.__name__ in names:
                res.append(elem)
        return res


def get_descendents(from_class, names_only=False):
    # Used to compute the possible models from a given top level
    # name
    if names_only:
        format_ = lambda x: x
    else:
        format_ = lambda x: (x, x)
    models = get_child_models(from_class)
    return map(lambda x: format_(x.__name__), models)


def get_module_name(cls):
    return cls.__name__.split('.')[0]


def change_relation_links(
        cls, from_module=None, to_module=None, convert_dict=None):
    for field_name in cls._fields.iterkeys():
        field = copy.copy(getattr(cls, field_name))
        attr_name = ''
        if hasattr(field, 'model_name'):
            attr_name = 'model_name'
        if hasattr(field, 'relation_name'):
            attr_name = 'relation_name'
        if hasattr(field, 'schema_model'):
            attr_name = 'schema_model'
        if attr_name == '':
            continue
        model_name = getattr(field, attr_name)
        if (convert_dict and not model_name in convert_dict or
            from_module and to_module and
                not (model_name.startswith(from_module)
                     and model_name.split('.', 1)[0] == from_module)):
            continue
        if convert_dict:
            converted_name = convert_dict[model_name]
        elif from_module and to_module:
            converted_name = to_module + model_name.split(from_module)[1]
        setattr(field, attr_name, converted_name)
        setattr(cls, field_name, field)


def to_list(data):
    if type(data) == list:
        return data
    elif type(data) == str:
        return [data]
    else:
        return [data]


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


def get_data_from_dict(data, dict):
    # This is used to parse a given dict for a set of data, and returns a dict
    # and a list of errors in the case it could not find one or more of the
    # specified data keys in the dict.
    res = ({}, [])
    for elem in data:
        if elem in dict:
            res[0][elem] = dict[elem]
        else:
            res[1] += '%s data not found' % elem
    return res


def convert_ref_to_obj(ref):
    # Currently (version 2.4), tryton does not convert automatically Reference
    # fields from string concatenation to browse objects.
    # That might evolve in the future, meanwhile this litlle method should make
    # it easier to do.
    #
    # Warning : it is not failsafe
    if isinstance(ref, Model):
        return ref
    try:
        model, id = ref.split(',')
    except Exception:
        raise
    model_obj = Pool().get(model)
    return model_obj(id)


def priority(priority_lvl):
    # This function is meant to be used as a decorator that will allow the
    # definition of priorities on other functions.
    # This is especially important in the case of before / post step methods
    # in the CoopProcess framework.
    #
    # USAGE :
    #    @priority(4)
    #    def my_func...
    def wrap(f):
        f.priority = priority_lvl
        return f
    return wrap


def keywords(keys):
    def wrap(f):
        f.keywords = keys
        return f
    return wrap


def limit_dates(dates, start=None, end=None):
    res = list(dates)
    res.sort()
    final_res = []
    for elem in res:
        if (not start or elem > start) and (not end or elem <= end):
            final_res.append(elem)
    if start and (not final_res or final_res[0] and final_res[0] != start):
        final_res.insert(0, start)
    if end and final_res[-1] != end:
        final_res.append(end)
    return final_res


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


def remove_tuple_from_list(cur_list, key):
    for cur_tuple in cur_list:
        if cur_tuple[0] == key:
            cur_list.remove(cur_tuple)
    return cur_list


def get_module_path(module_name):
    module_path = os.path.abspath(os.path.join(
        os.path.normpath(__file__), '..', '..', module_name))
    if os.path.isdir(module_path):
        return module_path


def get_coop_config(section, option):
    coop_utils = get_module_path('coop_utils')
    if coop_utils:
        config = ConfigParser.ConfigParser()
        config.read(os.path.join(coop_utils, 'coop.cfg'))
        return config.get(section, option)


def today():
    return Pool().get('ir.date').today()


def is_effective_at_date(instance, at_date=None, start_var_name='start_date',
        end_var_name='end_date'):
    if not at_date:
        at_date = today()
    start_date = None
    if hasattr(instance, start_var_name):
        start_date = getattr(instance, start_var_name)
    end_date = None
    if hasattr(instance, end_var_name):
        end_date = getattr(instance, end_var_name)
    return ((not start_date or at_date >= start_date)
        and (not end_date or at_date <= end_date))


def get_good_versions_at_date(instance, var_name, at_date=None,
        start_var_name='start_date', end_var_name='end_date'):
    '''This method looks for the elements in the list which are effective at
    the date. By default, it will check that the at_date is between the start
    date and the end_date, otherwise it will check if there is already a
    specific method on the object'''

    if not at_date:
        at_date = today()
    if hasattr(instance, 'get_good_versions_at_date'):
        return getattr(instance, 'get_good_versions_at_date')(
            var_name, at_date)
    res = []
    for elem in reversed(getattr(instance, var_name)):
        if is_effective_at_date(elem, at_date, start_var_name, end_var_name):
            res.insert(0, elem)
    return list(set(res))


def get_good_version_at_date(instance, var_name, at_date=None):
    res = get_good_versions_at_date(instance, var_name, at_date)
    if len(res) == 1:
        return res[0]


def add_frequency(frequency, to_date):
    if frequency == 'yearly':
        return to_date + relativedelta(years=+1)
    elif frequency == 'half-yearly':
        return to_date + relativedelta(months=+6)
    elif frequency == 'quarterly':
        return to_date + relativedelta(months=+3)
    elif frequency == 'monthly':
        return to_date + relativedelta(months=+1)


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


def get_relation_model(from_class_or_instance, field_name):
    model_name = get_relation_model_name(from_class_or_instance, field_name)
    if model_name:
        return Pool().get(model_name)


def instanciate_relation(from_class_or_instance, field_name):
    Model = get_relation_model(from_class_or_instance, field_name)
    if Model:
        return Model()


def create_inst_with_default_val(from_class, field_name, action=None):
    res = {}
    model_name = get_relation_model_name(from_class, field_name)
    CurModel = Pool().get(model_name)
    fields_names = list(x for x in set(CurModel._fields.keys())
        if x not in [
            'id', 'create_uid', 'create_date', 'write_uid', 'write_date'])
    field = getattr(from_class, field_name)
    if not isinstance(field, fields.Many2One):
        if action:
            res = {action: [CurModel.default_get(fields_names)]}
        else:
            res = [CurModel.default_get(fields_names)]
    else:
        res = CurModel.default_get(fields_names)
    return res


def append_inexisting(cur_list, item):
    if not item in cur_list:
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
            if not getattr(data, k, None):
                continue
            new_data = format_data(
                getattr(data, k), prefix + prefix_inc, is_init=False)
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
    if isinstance(pyson_expr, str):
        encoder = PYSONEncoder()
        the_pyson = encoder.encode(safe_eval(pyson_expr, CONTEXT))
    elif isinstance(pyson_expr, dict):
        encoder = PYSONEncoder()
        the_pyson = encoder.encode(safe_eval(str(pyson_expr), CONTEXT))
    elif pyson_expr is True:
        return True
    elif pyson_expr is False:
        return False
    else:
        the_pyson = target

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
    if not isinstance(field, fields.Many2One):
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
        if not key in field_name.states:
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
    field_name = copy.copy(getattr(cls, var_name))
    if not field_name.domain:
        field_name.domain = []
    field_name.domain.extend(new_domain)
    field_name.domain = list(set(field_name.domain))
    setattr(cls, var_name, field_name)


def get_team(good_user=None):
    if not good_user:
        User = Pool().get('res.user')
        good_user = User(Transaction().user)
    return good_user.team


def init_complementary_data(compl_data_defs):
    res = {}
    if compl_data_defs:
        for compl_data_def in compl_data_defs:
            res[compl_data_def.name] = compl_data_def.get_default_value(None)
    return res


def init_complementary_data_from_ids(ids):
    the_model = Pool().get('ins_product.complementary_data_def')
    res = {}
    for id in ids:
        elem = the_model(id)
        res[elem.name] = elem.get_default_value(None)
    return res


def get_complementary_data_value(
        instance, var_name, data_defs, at_date, value):
    res = None
    if hasattr(instance, var_name):
        cur_dict = getattr(instance, var_name)
        if cur_dict and value in cur_dict:
            res = cur_dict[value]
    if res:
        return res
    for data_def in data_defs:
        if data_def.name != value:
            continue
        if data_def.type_ in ['integer', 'float', 'numeric']:
            return 0


def execute_rule(caller, rule, args):
    args['_caller'] = caller
    return rule.compute(args)


def recursive_list_tuple_convert(the_list):
    if isinstance(the_list, (list, tuple)):
        return tuple((recursive_list_tuple_convert(x) for x in the_list))
    elif isinstance(the_list, dict):
        return dict((
            (key, recursive_list_tuple_convert(value))
            for key, value in the_list.iteritems()))
    else:
        return the_list


def is_none(instance, field_name):
    return (not hasattr(instance, field_name)
        or not getattr(instance, field_name))


def concat_res(res1, res2):
    res = list(res1)
    res[0] = res[0] and res2[0]
    res[1] += res2[1]
    return tuple(res)
