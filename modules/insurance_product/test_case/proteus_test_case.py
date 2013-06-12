#!/usr/bin/env python
# -*- coding: utf-8 -*-
from proteus import Model

from trytond.modules.rule_engine.test_case import create_or_update_folder
from trytond.modules.rule_engine.test_case import append_folder_to_context
from trytond.modules.rule_engine.test_case import get_or_create_context


def update_cfg(cfg_dict):
    cfg_dict['Context'] = Model.get('rule_engine.context')
    cfg_dict['TreeElement'] = Model.get('rule_engine.tree_element')


def launch_test_case(cfg_dict):
    update_cfg(cfg_dict)
    default_context = get_or_create_context(cfg_dict, 'Default Context')
    person_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.person')
    append_folder_to_context(default_context, person_folder)
    subscriber_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.subscriber')
    append_folder_to_context(default_context, subscriber_folder)
    contract_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.contract')
    append_folder_to_context(default_context, contract_folder)
    option_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.option')
    append_folder_to_context(default_context, option_folder)
    covered_data_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.covered_data')
    append_folder_to_context(default_context, covered_data_folder)
    rule_combination_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.rule_combination')
    append_folder_to_context(default_context, rule_combination_folder)
    rule_combi_context = get_or_create_context(cfg_dict, 'Rule Combination')
    rule_combination_folder = create_or_update_folder(cfg_dict,
        'ins_product.rule_sets.rule_combination')
    append_folder_to_context(rule_combi_context, rule_combination_folder)
