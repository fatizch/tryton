import multiprocessing

from proteus import config as pconfig


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
