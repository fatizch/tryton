#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

from proteus import Model, Wizard

import proteus_tools
import logging

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))
format = '[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
datefmt = '%a %b %d %H:%M:%S %Y'
logging.basicConfig(level=logging.INFO, format=format,
        datefmt=datefmt)
logging.getLogger('test_case').setLevel(logging.INFO)


def delete_db_if_necessary(cfg_dict):
    if cfg_dict['create_db']:
        db = os.path.join(
            cfg_dict['data_path'],
            proteus_tools.get_database_name(
                cfg_dict) + '.' + cfg_dict['db_type'])
        if os.path.isfile(db):
            logging.getLogger('test_case').info('Deleting DB : %s' % db)
            os.remove(db)


def install_modules(config, modules_to_install, cfg_dict, only_this_module):
    cfg_dict['_config'] = config
    if not only_this_module:
        will_be_installed = proteus_tools.get_modules_to_update(
            modules_to_install)
    else:
        will_be_installed = modules_to_install
    ConfigWizardItem = Model.get('ir.module.module.config_wizard.item')
    Module = Model.get('ir.module.module')
    installed_modules = set([x.name for x in
            Module.find([('state', '=', 'installed')])])
    for x in will_be_installed:
        if x in installed_modules:
            logging.getLogger('test_case').info('Module %s will be upgraded'
                % x)
        else:
            logging.getLogger('test_case').info('Module %s will be installed'
                % x)

    for cur_module in will_be_installed:
        module = Module.find([('name', '=', cur_module)])
        if module:
            logging.getLogger('test_case').info('Installing module %s' %
                cur_module)
            module = module[0]
            Module.install([module.id], config.context)
            Wizard('ir.module.module.install_upgrade').execute('upgrade')
            for item in ConfigWizardItem.find([('state', '!=', 'done')]):
                item.state = 'done'
                item.save()
    return installed_modules


def execute_test_cases(cfg_dict, files=False):
    if cfg_dict['only_install']:
        return
    wizard = Wizard('ir.test_case.run')
    if files:
        wizard.form.select_all_files = True
    else:
        wizard.form.select_all_test_cases = True
    wizard.execute('execute_test_cases')
    wizard.execute('end')


def launch_proteus_test_case(test_config_file=None, module=None):
    if not test_config_file:
        test_config_file = os.path.join(DIR, 'test_case.cfg')
    logging.getLogger('test_case').info('Reading config from %s'
        % test_config_file)
    cfg_dict = proteus_tools.get_test_cfg(test_config_file)

    delete_db_if_necessary(cfg_dict)
    if not module:
        modules = cfg_dict['modules']
    else:
        modules = [module]
    logging.getLogger('test_case').info('Installing requested Modules')
    install_modules(proteus_tools.get_config(cfg_dict),
        modules, cfg_dict, module is not None)
    return cfg_dict


if __name__ == '__main__':
    logging.getLogger('test_case').info('Launching Proteus Test Case')
    module = None
    if len(sys.argv) == 2:
        module = sys.argv[1]
    cfg_dict = launch_proteus_test_case(module=module)
    if not module and not cfg_dict['only_install']:
        Model.reset()
        execute_test_cases(cfg_dict)
        execute_test_cases(cfg_dict, files=True)
