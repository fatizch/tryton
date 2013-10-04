#!/usr/bin/env python
# -*- coding: utf-8 -*-

import random
import os
import logging
from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def get_models():
    res = {}
    res['Person'] = Model.get('party.party')
    return res


def update_persons(cfg_dict, models):
    n = 0
    for cur_pers in models['Person'].find([
                ('ssn', '=', None),
                ('is_person', '=', True),
            ]):
        if cur_pers.gender == 'male':
            ssn = '1'
        elif cur_pers.gender == 'female':
            ssn = '2'
        else:
            continue
        ssn = (ssn
            + cur_pers.birth_date.strftime('%y%m')
            + str(random.randint(1, 95)).zfill(2)
            + str(random.randint(1, 999)).zfill(3)
            + str(random.randint(1, 999)).zfill(3))
        key = str(97 - int(ssn) % 97).zfill(2)
        cur_pers.ssn = ssn + key
        cur_pers.save()
        n += 1
    if n > 0:
        logging.getLogger('test_case').info(
            'Successfully updated %s parties' % n)


def launch_test_case(cfg_dict):
    models = get_models()
    update_persons(cfg_dict, models)
