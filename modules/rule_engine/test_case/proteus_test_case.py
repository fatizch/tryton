#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Context'] = Model.get('rule_engine.context')
    cfg_dict['TreeElement'] = Model.get('rule_engine.tree_element')
    return cfg_dict


def get_object_from_db(cfg_dict, model, key=None, value=None, domain=None,
        force_search=False):
    if not force_search and cfg_dict['re_create_if_already_exists']:
        return None
    if not domain:
        domain = []
    if key and value:
        domain.append((key, '=', value))
    instances = cfg_dict[model].find(domain, limit=1)
    if instances:
        return instances[0]


def get_or_create_tree_element(cfg_dict, cur_type, description,
        translated_technical, name=None, namespace=None):
    cur_domain = []
    if cur_type == 'function':
        cur_domain.append(('namespace', '=', namespace))
        cur_domain.append(('name', '=', name))
    if cur_type == 'folder':
        cur_domain.append(('name', '=', name))
    cur_domain.append(('language.code', '=', cfg_dict['language']))
    cur_domain.append(('translated_technical_name', '=', translated_technical))
    tree_element = get_object_from_db(cfg_dict, 'TreeElement',
        domain=cur_domain)
    if tree_element:
        return tree_element
    lang = cfg_dict['Lang'].find([('code', '=', cfg_dict['language'])])[0]
    te = cfg_dict['TreeElement']()
    te.type = cur_type
    te.name = name
    te.description = description
    te.translated_technical_name = translated_technical
    te.namespace = namespace
    te.language = lang
    te.save()
    return te


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


def get_or_create_context(cfg_dict, name=None):
    ct = get_object_from_db(cfg_dict, 'Context', 'name', name)
    if ct:
        return ct
    if name:
        ct = cfg_dict['Context']()
        ct.name = name
        ct.save()
        return ct


def create_or_update_context(cfg_dict, name, allowed_elements):
    context = get_or_create_context(cfg_dict, name)
    for element in allowed_elements:
        if element and not element in context.allowed_elements:
            context.allowed_elements.append(element)
    context.save()


def create_default_context(cfg_dict):
    domain = [
        ('type', '=', 'folder'),
        ('description', '=', 'Tables'),
    ]
    te = get_object_from_db(cfg_dict, 'TreeElement', domain=domain)
    create_or_update_context(cfg_dict, 'Default Context', [te])


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    create_default_context(cfg_dict)
