#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import csv

from proteus import Model


def get_models():
    res = {}
    res['Insurer'] = Model.get('party.insurer')
    res['Society'] = Model.get('party.society')
    return res


def get_or_create_insurer(models, cfg_dict, code, name):
    insurers = models['Insurer'].find([('name', '=', name)])
    if len(insurers) > 0:
        return insurers[0]
    insurer = models['Insurer']()
    society = models['Society']()
    insurer.society.append(society)
    insurer.name = name
    insurer.code = code
    insurer.addresses[:] = []
    society.currency = cfg_dict['currency']
    insurer.save()
    return insurer


def create_insurers(models, cfg_dict):
    path = os.path.join(cfg_dict['dir_loc'], 'insurer')
    reader = csv.reader(open(path, 'rb'), delimiter=';')
    n = 0
    for insurer in reader:
        get_or_create_insurer(models, cfg_dict, insurer[0], insurer[1])
        n += 1

    print 'Successfully created %s insurers' % n


def launch_test_case(cfg_dict):
    models = get_models()
    create_insurers(models, cfg_dict)
