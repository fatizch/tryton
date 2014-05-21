#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import logging
from proteus import Model, Wizard

import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def generate_module_translation(cfg_dict, base_path, module_name):
    export_wizard = Wizard('ir.translation.export')
    wiz_form = export_wizard.form
    wiz_form.language, = Model.get('ir.lang').find(
        [('code', '=', cfg_dict['language'])])
    Module = Model.get('ir.module.module')
    try:
        wiz_form.module, = Module.find([('name', '=', module_name)])
    except ValueError:
        return
    export_wizard.execute('export')
    locale_dir = os.path.join(base_path, 'locale')
    result = export_wizard.form.file
    if not result:
        return
    if not os.path.exists(locale_dir):
        os.mkdir(locale_dir)
    po_path = os.path.join(locale_dir, '%s.po' % cfg_dict['language'])
    with open(po_path, 'w') as csv_file:
        logging.getLogger('export_translation').info('Generating translation '
            'file ' + po_path)
        csv_file.write(result)


def launch_proteus_test_case(test_config_file, modules):
    cfg_dict = proteus_tools.get_test_cfg(test_config_file)
    proteus_tools.get_config(cfg_dict)
    if not modules:
        modules = [x for x in os.listdir(os.path.join(DIR, '..', 'modules'))]
    for cur_module in modules:
        if cur_module == 'cog_translation':
            #Manual translations to override tryton translations
            continue
        cur_path = os.path.abspath(
            os.path.join(DIR, '..', 'modules', cur_module))
        if cfg_dict['un_fuzzy_translation']:
            un_fuzzy_translation(module=cur_module)
        generate_module_translation(cfg_dict, cur_path, cur_module)


def un_fuzzy_translation(src=None, module=None):
    Translation = Model.get('ir.translation')
    cur_domain = [('fuzzy', '=', True)]
    if module:
        cur_domain.append(('module', '=', module))
    if src:
        cur_domain.append(('src', '=', src))
    for cur_translation in Translation.find(cur_domain):
        cur_translation.fuzzy = False
        cur_translation.save()


def update_views(test_config_file):
    proteus_tools.get_config(proteus_tools.get_test_cfg(test_config_file))
    View = Model.get('ir.ui.view')
    View.write([x.id for x in View.find([])], {}, {})


if __name__ == '__main__':
    if len(sys.argv) > 1:
        modules = [sys.argv[1:]]
    else:
        modules = []
    launch_proteus_test_case(os.path.join(DIR, 'test_case.cfg'), modules)
