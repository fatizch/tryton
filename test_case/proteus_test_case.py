#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys

from proteus import Model, Wizard

import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))
CODE_TEMPLATE = '''def execute_test(cfg_dict):
    from %s import launch_test_case

    launch_test_case(cfg_dict)

execute_test(cfg_dict)
'''


def delete_db_if_necessary(cfg_dict):
    if cfg_dict['create_db']:
        db = os.path.join(
            cfg_dict['data_path'],
            proteus_tools.get_database_name(
                cfg_dict) + '.' + cfg_dict['db_type'])
        if os.path.isfile(db):
            print 'Deleting DB : %s' % db
            os.remove(db)


def install_modules(config, modules_to_install, cfg_dict):
    cfg_dict['_config'] = config
    will_be_installed = proteus_tools.get_modules_to_update(modules_to_install)
    ConfigWizardItem = Model.get('ir.module.module.config_wizard.item')
    Module = Model.get('ir.module.module')
    installed_modules = set()
    for cur_module in will_be_installed:
        module = Module.find([('name', '=', cur_module)])
        if module:
            module = module[0]
            Module.install([module.id], config.context)
            to_install = Module.find([('state', '=', 'to install')])
            installed_modules |= set([x.name for x in to_install])
            Wizard('ir.module.module.install_upgrade').execute('upgrade')
            Model.reset()
            for item in ConfigWizardItem.find([('state', '!=', 'done')]):
                item.state = 'done'
                item.save()
        if not cfg_dict['only_install']:
            update_modules(cfg_dict, [cur_module], True)
    return installed_modules


def get_module_cfg(path, cfg_dict):
    if not os.path.isfile(os.path.join(path, 'test_case', 'test_case.cfg')):
        return cfg_dict
    module_cfg = proteus_tools.get_cfg_as_dict(
        os.path.join(path, 'test_case', 'test_case.cfg'), 'options',
        ['depends'])
    if 'depends' in module_cfg.keys():
        for dependency in module_cfg['depends']:
            module_cfg = dict(get_module_cfg(
                os.path.abspath(
                    os.path.join(path, '..', 'modules', dependency)),
                cfg_dict).items() + module_cfg.items())
        module_cfg.pop('depends')
    return dict(cfg_dict.items() + module_cfg.items())


def load_test_case_translations(cfg_dict, path):
    import polib
    if not 'translate' in cfg_dict.keys():
        cfg_dict['translate'] = {}
    for po_file in [f for f in os.listdir(path) if f.endswith('.po')]:
        po = polib.pofile(os.path.join(path, po_file))
        for entry in po.translated_entries():
            cfg_dict['translate'][entry.msgid] = entry.msgstr
    return cfg_dict


def update_modules(cfg_dict, modules, only_this_module=False):
    cfg_dict = set_currency(cfg_dict)
    if not only_this_module:
        modules = proteus_tools.get_modules_to_update(modules)
    for cur_module in modules:
        print '=' * 80 + '\n'
        cur_path = os.path.abspath(
            os.path.join(DIR, '..', 'modules', cur_module))
        module_dict = get_module_cfg(cur_path, cfg_dict)
        module_dir = os.path.join(cur_path, 'test_case')
        if not os.path.isfile(os.path.join(
                module_dir, 'proteus_test_case.py')):
            print 'Missing test case file for module %s' % cur_module
            continue
        print 'Running test case for module % s' % cur_module

        code = CODE_TEMPLATE % ('trytond.modules.' + cur_module + '.test_case')
        module_dict = get_module_cfg(cur_path, cfg_dict)
        module_dict['dir'] = module_dir
        dir_loc = os.path.join(
            module_dir, module_dict.get('language', 'fr')[0:2].lower())
        if os.path.exists(dir_loc):
            module_dict['dir_loc'] = dir_loc
            module_dict = load_test_case_translations(
                module_dict, module_dict['dir_loc'])
        context = {'cfg_dict': module_dict}
        localcontext = {}
        exec code in context, localcontext


def import_json_files(cfg_dict):
    json_dir = os.path.join(
        DIR, 'json_files', cfg_dict.get('language', 'fr_FR'))
    if os.path.isdir(json_dir):
        files = [
            os.path.join(json_dir, f) for f in os.listdir(json_dir)
            if os.path.isfile(os.path.join(
                json_dir, f)) and f.endswith('.json')]
        if files:
            print ''
            print 'Loading json files'
        for cur_file in files:
            try:
                f = open(cur_file, 'rb')
                wizard = Wizard('coop_utils.import_wizard')
                wizard.form.selected_file = f.read()
                wizard.execute('file_import')
                f.close()
            except Exception as e:
                print 'Could not import %s' % cur_file
                print e
                continue
            print 'Successfully imported file %s' % cur_file


def launch_proteus_test_case(test_config_file=None, module=None):
    if not test_config_file:
        test_config_file = os.path.join(DIR, 'test_case.cfg')
    cfg_dict = proteus_tools.get_test_cfg(test_config_file)

    delete_db_if_necessary(cfg_dict)
    if not module:
        modules = cfg_dict['modules']
    else:
        modules = [module]
    installed_modules = install_modules(proteus_tools.get_config(cfg_dict),
        modules, cfg_dict)
    for cur_module in installed_modules:
        if cur_module in modules:
            print 'Module %s installed' % cur_module
        else:
            print 'Module %s already installed' % cur_module

    return cfg_dict


def set_currency(cfg_dict):
    Currency = Model.get('currency.currency')
    cur_domain = []
    if cfg_dict['currency']:
        if isinstance(cfg_dict['currency'], Model):
            return cfg_dict
        cur_domain.append(('code', '=', cfg_dict['currency']))
    currencies = Currency.find(cur_domain, limit=1)
    if len(currencies) > 0:
        cfg_dict['currency'] = currencies[0]
    return cfg_dict


if __name__ == '__main__':
    module = None
    if len(sys.argv) == 2:
        module = sys.argv[1]
    cfg_dict = launch_proteus_test_case(module=module)
    if not module and not cfg_dict['only_install']:
        import_json_files(cfg_dict)
