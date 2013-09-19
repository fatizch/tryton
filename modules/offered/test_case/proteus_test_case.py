#!/usr/bin/env python
# -*- coding: utf-8 -*-
import proteus_tools
from proteus import Model


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Company'] = Model.get('company.company')
    cfg_dict['User'] = Model.get('res.user')


def launch_test_case(cfg_dict):
    update_cfg_dict_with_models(cfg_dict)
    company_candidates = cfg_dict['Company'].find([])
    if company_candidates:
        company = company_candidates[0]
    else:
        company = proteus_tools.get_or_create_company(
            cfg_dict, 'Coop')
    cfg_dict['User'].write([x.id for x in cfg_dict['User'].find([])], {
            'main_company': company.id}, {})

    proteus_tools.set_global_search('offered.product')
