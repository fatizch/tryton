#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import csv
from proteus import Model
import proteus_tools

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_models(cfg_dict):
    cfg_dict['Country'] = Model.get('country.country')
    cfg_dict['ZipCode'] = Model.get('country.zipcode')
    return cfg_dict


def load_zipcode(cfg_dict):
    country_code = cfg_dict.get('language', 'fr')[0:2]
    country = cfg_dict['Country'].find(
        [('code', '=', country_code.upper())])[0]
    path = os.path.join(DIR, country_code.lower(), 'zipcode.csv')
    reader = csv.reader(open(path, 'rb'), dialect='excel-tab')
    n = 0
    for cur_line in reader:
        if len(cur_line) < 2:
            continue
        if (cfg_dict['load_all_zipcode']
                or cur_line[1][0:2] in eval(cfg_dict['zip'])):
            zip = cur_line[1].rstrip().lstrip()
            city = cur_line[0].rstrip().lstrip()
            proteus_tools.get_or_create_this({
                    'city': city,
                    'zip': zip,
                    'country': country,
                }, cfg_dict, 'ZipCode', domain=['country', 'zip', 'city'])
            n += 1
    print 'Successfully created %s %s' % (n, 'ZipCode')


def launch_test_case(cfg_dict):
    cfg_dict = update_models(cfg_dict)
    load_zipcode(cfg_dict)


def is_table_empty(model):
    return len(model.find(limit=1)) == 0
