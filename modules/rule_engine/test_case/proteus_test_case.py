#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from proteus import Model
import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Context'] = Model.get('rule_engine.context')
    cfg_dict['TreeElement'] = Model.get('rule_engine.tree_element')
    cfg_dict['Table'] = Model.get('table.table_def')
    return cfg_dict


def get_or_create_context(cfg_dict, name=None):
    ct = proteus_tools.get_objects_from_db(cfg_dict, 'Context', 'name', name)
    if ct:
        return ct
    if name:
        ct = cfg_dict['Context']()
        ct.name = name
        proteus_tools.try_to_save_object(cfg_dict, ct)
        return ct


def get_or_create_tree_element(
        cfg_dict, cur_type, description, translated_technical,
        fct_args='', name=None, namespace=None, long_desc=''):
    cur_domain = []
    if cur_type == 'function':
        cur_domain.append(('namespace', '=', namespace))
        cur_domain.append(('name', '=', name))
    if cur_type == 'folder':
        cur_domain.append(('description', '=', description))
    cur_domain.append(('language.code', '=', cfg_dict['language']))
    cur_domain.append(('translated_technical_name', '=', translated_technical))
    tree_element = proteus_tools.get_objects_from_db(
        cfg_dict, 'TreeElement', domain=cur_domain)
    if tree_element:
        return tree_element
    lang = cfg_dict['Lang'].find([('code', '=', cfg_dict['language'])])[0]
    te = cfg_dict['TreeElement']()
    if fct_args:
        te.fct_args = ', '.join(map(
            proteus_tools.remove_all_but_alphanumeric_and_space,
            fct_args.split(',')))
    te.translated_technical_name = translated_technical
    te.description = description
    te.long_description = long_desc
    te.type = cur_type
    te.name = name
    te.namespace = namespace
    te.language = lang
    proteus_tools.try_to_save_object(cfg_dict, te)
    return te


def create_or_update_folder(cfg_dict, set_name):
    descs = parse_tree_names(cfg_dict)
    tes = []
    for name, vals in descs[set_name].iteritems():
        if name == set_name:
            continue
        cur_te = get_or_create_tree_element(cfg_dict, 'function', vals[0],
            vals[1], vals[2], name, set_name, vals[3])
        tes.append(cur_te)
    te_top = get_or_create_tree_element(cfg_dict, 'folder',
        descs[set_name][set_name][0], descs[set_name][set_name][1])
    proteus_tools.append_inexisting_elements(te_top, 'children', tes)
    te_top.save()
    return te_top


def parse_tree_names(cfg_dict):
    base_data = proteus_tools.read_data_file(
        os.path.join(cfg_dict['dir_loc'], 'tree_names'))

    final_data = {}
    for k, v in base_data.iteritems():
        if not k in final_data:
            final_data[k] = {}

        for elem in v:
            final_data[k][elem[0]] = elem[1:]

    return final_data


def append_folder_to_context(the_context, the_folder):
    proteus_tools.append_inexisting_elements(the_context, 'allowed_elements',
        [the_folder])
    the_context.save()


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    default_context = get_or_create_context(cfg_dict, 'Default Context')
    func_folder = create_or_update_folder(cfg_dict,
        'rule_engine.tools_functions')
    append_folder_to_context(default_context, func_folder)
    table_folder = get_or_create_tree_element(cfg_dict, 'folder', 'Tables',
        'table_folder')
    lang = Model.get('ir.lang').find([('code', '=', cfg_dict['language'])])[0]
    for table in cfg_dict['Table'].find([]):
        table_elem = cfg_dict['TreeElement']()
        table_elem.language = lang
        table_elem.type = 'table'
        table_elem.parent = table_folder
        table_elem.the_table = table
        table_elem.save()
    print '#' * 80
    print 'WRITE §§§§§§§§'
    cfg_dict['Table'].write([t.id for t in cfg_dict['Table'].find([])], {}, {})
    append_folder_to_context(default_context, table_folder)
