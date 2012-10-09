#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import random
from proteus import Model
DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['Table'] = Model.get('indice_table.definition')
    cfg_dict['Dimension'] = Model.get('indice_table.definition.dimension')
    cfg_dict['Cell'] = Model.get('indice_table')
    return cfg_dict


def create_dimension(cfg_dict, _type, value=None, start=None, end=None,
    start_date=None, end_date=None):
    res = cfg_dict['Dimension']()
    res.type = _type
    res.value = str(value)
    res.start = start
    res.end = end
    res.start_date = start_date
    res.end_date = end_date
    return res


def create_table(cfg_dict, name, dim1_kind, dim1,
    dim2_kind=None, dim2=None, dim3_kind=None, dim3=None):
    res = cfg_dict['Table']()
    res.name = name
    res.dimension_kind1 = dim1_kind
    for i in dim1:
        res.dimension1.append(create_dimension(cfg_dict, 'dimension1', i))
    if dim2_kind:
        res.dimension_kind2 = dim2_kind
        for i in dim2:
            res.dimension2.append(create_dimension(cfg_dict, 'dimension2', i))
    if dim3_kind:
        res.dimension_kind3 = dim3_kind
        for i in dim3:
            res.dimension2.append(create_dimension(cfg_dict, 'dimension2', i))
    return res


def create_cell(cfg_dict, table, value, dim1, dim2=None, dim3=None):
    res = cfg_dict['Cell']()
    res.definition = table
    res.dimension1 = dim1
    res.dimension2 = dim2
    res.dimension3 = dim3
    res.value = str(value)
    res.save()
    return res


def create_objects(cfg_dict):
    table = create_table(cfg_dict, 'Table 10x100', 'value', range(100),
    'value', range(10))
    table.save()
    for dim1 in table.dimension1:
        for dim2 in table.dimension2:
            create_cell(cfg_dict, table, random.random() * 100, dim1, dim2)


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    create_objects(cfg_dict)
