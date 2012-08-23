#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import ConfigParser
import warnings
from proteus import Model, Wizard
from proteus import config as pconfig


DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))
CODE_TEMPLATE = '''def execute_test():
    from %s import launch_test_case

    launch_test_case()

execute_test()
'''


def install_modules(config, modules_to_install):
    Module = Model.get('ir.module.module')
    modules = Module.find([
        ('name', 'in', modules_to_install),
        ('state', '!=', 'installed'),
    ])
    Module.install([x.id for x in modules], config.context)
    modules = [x.name for x in Module.find([('state', '=', 'to install')])]
    Wizard('ir.module.module.install_upgrade').execute('upgrade')

    ConfigWizardItem = Model.get('ir.module.module.config_wizard.item')
    for item in ConfigWizardItem.find([('state', '!=', 'done')]):
        item.state = 'done'
        item.save()

    return modules


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
    cfg_dict['config_file'] = os.path.abspath(
            os.path.join(DIR, cfg_dict['config_file'], 'trytond.conf'))

    trytond_cfg_dict = get_cfg_as_dict(cfg_dict['config_file'], 'options')

    return dict(cfg_dict.items() + trytond_cfg_dict.items())


def delete_db_if_necessary(cfg_dict):
    if cfg_dict['create_db']:
        db = os.path.join(cfg_dict['data_path'],
            cfg_dict['database_name'] + '.' + cfg_dict['db_type'])
        if os.path.isfile(db):
            print 'Deleting DB : %s' % db
            os.remove(db)


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


def install_or_update_modules(from_modules):
    modules = get_modules_to_update(from_modules)
    for cur_module in modules:
        print '=' * 80
        cur_file = os.path.abspath(
            os.path.join(DIR, '..', cur_module, 'test_case',
                'proteus_test_case.py'))
        if not os.path.isfile(cur_file):
            print 'Missing test case file for module %s' % cur_module
            continue
        print 'Running test case for module % s' % cur_module
        code = CODE_TEMPLATE % ('trytond.modules.' + cur_module + '.test_case')
        try:
            exec code
        except:
            warnings.warn('KO : Exception raised', stacklevel=2)


def launch_proteus_test_case(test_config_file):
    cfg_dict = get_test_cfg(test_config_file)

    delete_db_if_necessary(cfg_dict)

    config = pconfig.set_trytond(
        database_name=cfg_dict['database_name'],
        user=cfg_dict['user'],
        database_type=cfg_dict['db_type'],
        language=cfg_dict['language'],
        password=cfg_dict['password'],
        config_file=cfg_dict['config_file'],
        )

    modules = install_modules(config, cfg_dict['modules'])
    for module in cfg_dict['modules']:
        if module in modules:
            print 'Module %s installed' % module
        else:
            print 'Module %s already installed' % module

    install_or_update_modules(cfg_dict['modules'])


if __name__ == '__main__':
    launch_proteus_test_case('test.cfg')
