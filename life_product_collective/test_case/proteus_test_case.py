#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from proteus import Model
import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_models(cfg_dict):
    cfg_dict['College'] = Model.get('party.college')
    cfg_dict['Tranche'] = Model.get('tranche.tranche')
    return cfg_dict


def get_or_create_college(cfg_dict, code=None, name=None, tranches=None):
    res = proteus_tools.get_objects_from_db(cfg_dict, 'College', 'name', name)
    if res:
        return res
    res = cfg_dict['College']()
    res.code = code
    res.name = name
    if tranches:
        res.tranches[:] = tranches
    res.save()


def create_colleges(cfg_dict):
    TA = proteus_tools.get_objects_from_db(cfg_dict, 'Tranche', 'code', 'TA')
    TB = proteus_tools.get_objects_from_db(cfg_dict, 'Tranche', 'code', 'TB')
    TC = proteus_tools.get_objects_from_db(cfg_dict, 'Tranche', 'code', 'TC')
    TD = proteus_tools.get_objects_from_db(cfg_dict, 'Tranche', 'code', 'TD')
    T1 = proteus_tools.get_objects_from_db(cfg_dict, 'Tranche', 'code', 'T1')
    T2 = proteus_tools.get_objects_from_db(cfg_dict, 'Tranche', 'code', 'T2')
    get_or_create_college(cfg_dict, 'C', 'Cadre', [TA, TB, TC, TD])
    get_or_create_college(cfg_dict, 'NC', 'Non Cadre', [T1, T2])
    get_or_create_college(cfg_dict, 'EP', 'Ensemble du Personnel',
        [TA, TB, TC, TD, T1, T2])


def launch_test_case(cfg_dict):
    cfg_dict = update_models(cfg_dict)
    create_colleges(cfg_dict)
