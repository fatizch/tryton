#!/usr/bin/env python
# -*- coding: utf-8 -*-


from proteus import Model
import proteus_tools


def update_models(cfg_dict):
    pass


def launch_test_case(cfg_dict):
    update_models(cfg_dict)
    proteus_tools.set_global_search('ins_product.product')
