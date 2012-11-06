#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import ConfigParser
from proteus import Model, Wizard
from proteus import config as pconfig
import logging.handlers
import time
import sys


DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))
CODE_TEMPLATE = '''def execute_test(cfg_dict):
    from %s import launch_test_case

    launch_test_case(cfg_dict)

execute_test(cfg_dict)
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


def get_module_cfg(path, cfg_dict):
    if not os.path.isfile(os.path.join(path, 'test_case', 'test_case.cfg')):
        return cfg_dict
    module_cfg = get_cfg_as_dict(
        os.path.join(path, 'test_case', 'test_case.cfg'), 'options',
        ['depends'])
    if 'depends' in module_cfg.keys():
        for dependency in module_cfg['depends']:
            module_cfg = dict(get_module_cfg(
                    os.path.abspath(os.path.join(path, '..', dependency)),
                    cfg_dict).items()
                + module_cfg.items())
        module_cfg.pop('depends')
    return dict(cfg_dict.items() + module_cfg.items())


def generate_module_translation(cfg_dict, base_path, module_name):
    export_wizard = Wizard('ir.translation.export')
    wiz_form = export_wizard.form
    wiz_form.language, = Model.get('ir.lang').find(
        [('code', '=', cfg_dict['language'])])
    Module = Model.get('ir.module.module')
    wiz_form.module, = Module.find([('name', '=', module_name)])
    export_wizard.execute('export')
    locale_dir = os.path.join(base_path, 'locale')
    if not os.path.exists(locale_dir):
        os.mkdir(locale_dir)
    po_path = os.path.join(locale_dir, '%s.po' % cfg_dict['language'])
    with open(po_path, 'w') as csv_file:
        print 'Generating translation file ', po_path
        csv_file.write(export_wizard.form.file)


def update_modules(cfg_dict):
    cfg_dict = set_currency(cfg_dict)
    modules = get_modules_to_update(cfg_dict['modules'])
    for cur_module in modules:
        print '=' * 80 + '\n'
        cur_path = os.path.abspath(
            os.path.join(DIR, '..', cur_module))
        if cfg_dict['un_fuzzy_translation']:
            un_fuzzy_translation(module=cur_module)
        if cfg_dict['export_translation']:
            generate_module_translation(cfg_dict, cur_path, cur_module)
        if not cfg_dict['create_data']:
            continue
        if not os.path.isfile(os.path.join(
                    cur_path, 'test_case', 'proteus_test_case.py')):
            print 'Missing test case file for module %s' % cur_module
            continue
        print 'Running test case for module % s' % cur_module

        code = CODE_TEMPLATE % ('trytond.modules.' + cur_module + '.test_case')
        #try:
        context = {'cfg_dict': get_module_cfg(cur_path, cfg_dict)}
        localcontext = {}
        exec code in context, localcontext
        #except:
        #    warnings.warn('KO : Exception raised', stacklevel=2)


def get_config(cfg_dict):
    print cfg_dict
    logf = cfg_dict.get('logfile', None)

    if logf:
        print logf
        format = '[%(asctime)s] %(levelname)s:%(name)s:%(message)s'
        datefmt = '%a %b %d %H:%M:%S %Y'
        logging.basicConfig(level=logging.INFO, format=format,
                datefmt=datefmt)

        # test if the directories exist, else create them
        try:
            diff = 0
            if os.path.isfile(logf):
                diff = int(time.time()) - int(os.stat(logf)[-1])
            handler = logging.handlers.TimedRotatingFileHandler(
                logf, 'D', 1, 30)
            handler.rolloverAt -= diff
        except Exception, exception:
            sys.stderr.write(\
                    "ERROR: couldn't create the logfile directory:" \
                    + str(exception))
        else:
            formatter = logging.Formatter(format, datefmt)
            # tell the handler to use this format
            handler.setFormatter(formatter)

            # add the handler to the root logger
            logging.getLogger().addHandler(handler)
            logging.getLogger().setLevel(logging.INFO)

    return pconfig.set_trytond(
        database_name=cfg_dict['database_name'],
        user=cfg_dict['user'],
        database_type=cfg_dict['db_type'],
        language=cfg_dict['language'],
        password=cfg_dict['password'],
        config_file=cfg_dict['config_file'],
    )


def launch_proteus_test_case(test_config_file):
    cfg_dict = get_test_cfg(test_config_file)

    delete_db_if_necessary(cfg_dict)

    modules = install_modules(get_config(cfg_dict), cfg_dict['modules'])
    for module in cfg_dict['modules']:
        if module in modules:
            print 'Module %s installed' % module
        else:
            print 'Module %s already installed' % module

    update_modules(cfg_dict)


def un_fuzzy_translation(src=None, module=None):
    Translation = Model.get('ir.translation')
    cur_domain = [('fuzzy', '=', True)]
    if module:
        cur_domain.append(('module', '=', module))
    if src:
        cur_domain.append(('src', '=', src))
    for cur_translation in Translation.find(cur_domain):
        cur_translation.fuzzy = False
        print 'unfuzzy %s in %s' % (
            cur_translation.src, cur_translation.name)
        cur_translation.save()


def set_currency(cfg_dict):
    Currency = Model.get('currency.currency')
    cur_domain = []
    if cfg_dict['currency']:
        cur_domain.append(('code', '=', cfg_dict['currency']))
    currencies = Currency.find(cur_domain, limit=1)
    if len(currencies) > 0:
        cfg_dict['currency'] = currencies[0]
    return cfg_dict

if __name__ == '__main__':
    launch_proteus_test_case(os.path.join(DIR, 'test_case.cfg'))
