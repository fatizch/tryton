import os
import multiprocessing
import functools
import ConfigParser
import logging.handlers
import time
import sys

from proteus import Model
from proteus import config as pconfig

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def get_config(cfg_dict):
    logf = cfg_dict.get('logfile', None)

    if logf:
        format = '[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
        datefmt = '%a %b %d %H:%M:%S %Y'
        logging.basicConfig(
            level=logging.INFO, format=format, datefmt=datefmt)

        # test if the directories exist, else create them
        try:
            diff = 0
            if os.path.isfile(logf):
                diff = int(time.time()) - int(os.stat(logf)[-1])
            handler = logging.handlers.TimedRotatingFileHandler(
                logf, 'D', 1, 30)
            handler.rolloverAt -= diff
        except Exception, exception:
            sys.stderr.write(
                "ERROR: couldn't create the logfile directory:"
                + str(exception))
        else:
            formatter = logging.Formatter(format, datefmt)
            # tell the handler to use this format
            handler.setFormatter(formatter)

            # add the handler to the root logger
            logging.getLogger().addHandler(handler)
            logging.getLogger().setLevel(logging.INFO)

    return pconfig.set_trytond(
        database_name=get_database_name(cfg_dict),
        user=cfg_dict['user'],
        database_type=cfg_dict['db_type'],
        language=cfg_dict['language'],
        password=cfg_dict['password'],
        config_file=cfg_dict['config_file'],
    )


def get_database_name(cfg_dict):
    if 'database_name' in cfg_dict:
        return cfg_dict['database_name']
    config_file = os.path.join(cfg_dict['config_path'], 'scripts.conf')
    if os.path.isfile(config_file):
        with open(config_file, 'r') as f:
            for line in f.readlines():
                if line.startswith('DATABASE_NAME'):
                    return line.split('=')[1].strip()


def multi_launch(the_fun, the_args, connexion_date):
    while the_args:
        the_fun(*(the_args.pop()))


def npop(the_list, n):
    res = []
    for i in range(n):
        if len(the_list) > 0:
            res.append(the_list.pop())
        else:
            break
    return res


def multiprocess_this(fun, the_args, cfg_dict, connexion_date):
    # num_processes = multiprocessing.cpu_count()
    num_processes = 1

    grouping = int((len(the_args) - 1) / num_processes) + 1

    print 'Num processes : %s' % num_processes
    print 'Grouping : %s' % grouping
    print 'Number of args : %s\n' % len(the_args)

    get_config(cfg_dict, connexion_date)

    for n in range(num_processes):
        p = multiprocessing.Process(target=multi_launch, args=(
            fun,
            npop(the_args, grouping),
            connexion_date))
        p.start()
        p.join()
        print 'Number of args remaining : %s' % len(the_args)


def get_objects_from_db(
        cfg_dict, model, key=None, value=None, domain=None,
        force_search=False, limit=1):
    if not force_search and cfg_dict['re_create_if_already_exists']:
        return None
    if not domain:
        domain = []
    if key and value:
        domain.append((key, '=', value))

    if not cfg_dict[model]:
        return None
    instances = cfg_dict[model].find(domain, limit=limit)
    if instances and limit == 1:
        return instances[0]
    else:
        return instances


def get_or_create_this(
        data, ctx={}, cfg_dict={}, class_key='', sel_val='', domain=None,
        to_store=True, only_get=False):
    if sel_val:
        the_object = get_objects_from_db(
            cfg_dict, class_key, sel_val, data[sel_val])
    elif domain:
        def prepare_search(data):
            if isinstance(data, Model):
                return data.id
            return data

        the_object = get_objects_from_db(
            cfg_dict, class_key, domain=[
                ('%s' % k, '=', prepare_search(data[k]))
                for k in domain
                if k in data])

    if the_object:
        return the_object
    elif only_get:
        return None

    with cfg_dict[class_key]._config.set_context(ctx):
        the_object = cfg_dict[class_key]()

        for key, value in data.iteritems():
            try:
                if isinstance(value, list):
                    proteus_append_extend(the_object, key, value)
                else:
                    setattr(the_object, key, value)
            except AttributeError:
                print key
                print value
                raise

        if to_store:
            the_object.save()

    return the_object


def append_from_key(cfg_dict, from_obj, list_name, object_class_key, key,
        values):
    '''
    This function allows to add instances to a list from their functional key
    object_class_key is the cfg_dict key for the model of instances we are
    trying to set on the list
    '''
    if not values:
        return
    to_list = getattr(from_obj, list_name)
    for code in values:
        if not code in [x.code for x in to_list]:
            event_obj = get_objects_from_db(
                cfg_dict, object_class_key, key, code)
            if event_obj:
                to_list.append(event_obj)
    from_obj.save()


def generate_creation_method(
        cfg_dict, class_key, sel_val='', domain=None,
        to_store=True, only_get=False):
    return functools.partial(
        get_or_create_this,
        cfg_dict=cfg_dict,
        class_key=class_key,
        sel_val=sel_val,
        domain=domain,
        to_store=to_store,
        only_get=only_get)


def get_translation(string, cfg_dict):
    return cfg_dict['translate'].get(string, string)


def translate_this(cfg_dict):
    return functools.partial(get_translation, cfg_dict=cfg_dict)


def write_data_file(filename, data):
    the_file = open(filename, 'w')
    the_file.write('\n'.join(data))
    the_file.close


def read_data_file(filename, sep='|'):
    res = {}
    cur_model = ''
    cur_data = []
    lines = open(filename).readlines()
    for line in lines:
        line = line[:-1]
        line.rstrip()
        if line == '':
            continue
        if line[0] == '[' and line[-1] == ']':
            if cur_model and cur_data:
                res[cur_model] = cur_data
            cur_model = line[1:-1]
            cur_data = []
            continue
        cur_data.append(line.split(sep))

    res[cur_model] = cur_data

    return res


def proteus_append_extend(obj, field, data):
    if isinstance(data, list):
        tmp_list = []
        for elem in data:
            tmp_list.append(elem.__class__(elem.id))
    else:
        tmp_list = [data]

    getattr(obj, field).extend(tmp_list)


def create_zip_code_if_necessary(address):
    if not (address.zip and address.country and address.city):
        return
    Zip = Model.get('country.zipcode')
    domain = [
        ('city', '=', address.city),
        ('zip', '=', address.zip),
        ('country', '=', address.country.id)
    ]
    if Zip.find(domain):
        return
    zipcode = Zip()
    zipcode.city = address.city
    zipcode.country = address.country
    zipcode.zip = address.zip
    zipcode.save()


def get_cfg_as_dict(cfg, section, items_as_list=None):
    '''this function get a config file as input and convert the section into
    a dictionnary.
    All items given in the items_as_list will be converted as list
    [config]
    database_type = sqlite
    modules:
        insurance_party
        insurance_product

    get_cfg_as_dict(cfg, 'config', ['modules'])'''

    cfg_parser = ConfigParser.ConfigParser()
    with open(cfg) as fp:
        cfg_parser.readfp(fp)
    cfg_dict = dict(cfg_parser.items(section))

    #Setting the items as list
    if items_as_list:
        for key in items_as_list:
            if key in cfg_dict:
                cfg_dict[key] = cfg_dict[key].strip().splitlines()

    #Setting boolean values
    for (key, value) in cfg_dict.items():
        try:
            if value.upper() == 'TRUE':
                cfg_dict[key] = True
            if value.upper() == 'FALSE':
                cfg_dict[key] = False
        except:
            pass

    return cfg_dict


def get_test_cfg(test_config_file):
    cfg_dict = get_cfg_as_dict(test_config_file, 'options', ['modules'])
    cfg_dict['config_path'] = os.path.abspath(
        os.path.join(DIR, cfg_dict['config_path']))
    cfg_dict['config_file'] = os.path.abspath(
        os.path.join(DIR, cfg_dict['config_path'], 'trytond.conf'))

    trytond_cfg_dict = get_cfg_as_dict(cfg_dict['config_file'], 'options')

    return dict(cfg_dict.items() + trytond_cfg_dict.items())


def get_module_depends(module):
    from trytond.modules import get_module_info

    res = set()
    info = get_module_info(module)
    for dependency in info.get('depends', []):
        res |= set(get_module_depends(dependency))
    res.add(module)
    return list(res)


def is_coop_module(module):
    return 'coop_utils' in get_module_depends(module)


def get_modules_to_update(from_modules):
    from trytond.modules import create_graph

    modules_set = set()
    for cur_module in from_modules:
        modules_set |= set(get_module_depends(cur_module))
    graph = create_graph(list(modules_set))[0]
    return [x.name for x in graph if is_coop_module(x.name)]


def remove_all_but_alphanumeric_and_space(from_string):
    import re
    pattern = re.compile(r'([^\s\w]|_)+')
    return pattern.sub('', from_string)


def convert_to_reference(value):
    if isinstance(value, Model):
        value = '%s,%s' % (value.__class__.__name__, value.id)
    return value or None


def set_global_search(model_name):
    model = get_objects_from_db(
        {'Model': Model.get('ir.model')},
        'Model', 'model', model_name, force_search=True)
    if not model.global_search_p:
        model.global_search_p = True
        model.save()


def append_inexisting_elements(cur_object, list_name, the_list):
    to_set = False
    if hasattr(cur_object, list_name):
        cur_list = getattr(cur_object, list_name)
        if cur_list is None:
            cur_list = []
            to_set = True

    if not isinstance(the_list, (list, tuple)):
        the_list = [the_list]

    for child in the_list:
        if not child in cur_list:
            cur_list.append(child)

    if to_set:
        setattr(cur_object, list_name, cur_list)

    cur_object.save()
    return cur_object


def try_to_save_object(cfg_dict, cur_object):
    if not cfg_dict['re_create_if_already_exists']:
        cur_object.save()
    #if we try to save one object which already exists, we could have error
    #with constraints
    try:
        cur_object.save()
    except:
        print 'Exception raised when trying to save', cur_object
