import multiprocessing
import functools

from proteus import config as pconfig
from proteus import Model


def get_config(cfg_dict, connexion_date):
    config = pconfig.set_trytond(
        database_name=cfg_dict['database_name'],
        user=cfg_dict['user'],
        database_type=cfg_dict['db_type'],
        language=cfg_dict['language'],
        password=cfg_dict['password'],
        config_file=cfg_dict['config_file'],
    )
    config.set_context({'client_defined_date': connexion_date})
    return config


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
#    num_processes = multiprocessing.cpu_count()
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


def get_objects_from_db(cfg_dict, model, key=None, value=None, domain=None,
        force_search=False, limit=1):
    if not force_search and cfg_dict['re_create_if_already_exists']:
        return None
    if not domain:
        domain = []
    if key and value:
        domain.append((key, '=', value))

    instances = cfg_dict[model].find(domain, limit=limit)
    if instances and limit == 1:
        return instances[0]
    else:
        return instances


def get_or_create_this(data, cfg_dict, class_key, sel_val='', domain=None,
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

    the_object = cfg_dict[class_key]()

    for key, value in data.iteritems():
        try:
            if isinstance(value, list):
                getattr(the_object, key).extend(value)
            else:
                setattr(the_object, key, value)
        except AttributeError:
            print key
            print value
            raise

    if to_store:
        the_object.save()

    return the_object


def generate_creation_method(cfg_dict, class_key, sel_val='', domain=None,
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
