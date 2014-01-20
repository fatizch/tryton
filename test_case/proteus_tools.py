import os
import ConfigParser
import logging.handlers
import time
import sys
from proteus import config as pconfig

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def get_config(cfg_dict):
    logf = cfg_dict.get('logfile', None)

    if logf:
        format = '[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
        datefmt = '%a %b %d %H:%M:%S %Y'
        logging.basicConfig(
            level=logging.WARNING, format=format, datefmt=datefmt)

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
            logging.getLogger().setLevel(logging.WARNING)

    return pconfig.set_trytond(
        database_name=get_database_name(cfg_dict),
        user=cfg_dict['user'],
        database_type=cfg_dict['db_type'],
        language=cfg_dict['language'],
        password=cfg_dict['password'],
        config_file=cfg_dict['config_file'],
    )


def get_cfg_as_dict(cfg, section, items_as_list=None):
    '''this function get a config file as input and convert the section into
    a dictionnary.
    All items given in the items_as_list will be converted as list
    [config]
    database_type = sqlite
    modules:
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


def is_coop_module(module):
    return 'cog_utils' in get_module_depends(module)


def get_module_depends(module):
    # Very bad performances, especially since it is recursive. Consider moving
    # import at the top
    from trytond.modules import get_module_info

    res = set()
    info = get_module_info(module)
    for dependency in info.get('depends', []):
        res |= set(get_module_depends(dependency))
    res.add(module)
    return list(res)


def get_modules_to_update(from_modules):
    from trytond.modules import create_graph

    modules_set = set()
    for cur_module in from_modules:
        modules_set |= set(get_module_depends(cur_module))
    graph = create_graph(list(modules_set))[0]
    return [x.name for x in graph if is_coop_module(x.name)]


def get_database_name(cfg_dict):
    if 'DB_NAME' in os.environ:
        return os.environ['DB_NAME']
    if 'database_name' in cfg_dict:
        return cfg_dict['database_name']
    config_file = os.path.join(cfg_dict['config_path'], 'scripts.conf')
    if os.path.isfile(config_file):
        with open(config_file, 'r') as f:
            for line in f.readlines():
                if line.startswith('DATABASE_NAME'):
                    return line.split('=')[1].strip()
