#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import csv
import datetime
from proteus import Model
from decimal import Decimal


def update_cfg_dict_with_models(cfg_dict):
    cfg_dict['TaxDesc'] = Model.get('coop_account.tax_desc')
    cfg_dict['TaxVersion'] = Model.get('coop_account.tax_version')
    return cfg_dict


def get_or_create_tax_desc(cfg_dict, code=None, name=None, desc=None):
    cur_domain = []
    if name:
        cur_domain.append(('name', '=', name))
    if code:
        cur_domain.append(('code', '=', code))
    taxes = cfg_dict['TaxDesc'].find(cur_domain)
    if len(taxes) > 0:
        return taxes[0]
    res = cfg_dict['TaxDesc']()
    res.code = code
    res.name = name
    res.description = desc
    return res


def get_tax_version(tax, value):
    for version in tax.versions:
        if str(version.value) == value:
            return version


def get_previous_version(tax, at_date):
    prev_version = None
    for version in tax.versions:
        if version.start_date > at_date:
            return prev_version
        prev_version = version
    return prev_version


def append_version(tax, version):
    rank = 0
    prev_version = get_previous_version(tax, version.start_date)
    if prev_version:
        prev_version.end_date = version.start_date - datetime.timedelta(days=1)
        rank = tax.versions.index(prev_version) + 1
    cur_list = list(tax.versions)
    cur_list.insert(rank, version)
    tax.versions[:] = cur_list
    return tax


def get_or_create_objects(cfg_dict, line):
    tax = get_or_create_tax_desc(cfg_dict, line[0], line[1], line[5])
    tax_version = get_tax_version(tax, line[3])
    if tax_version:
        return tax_version
    tax_version = cfg_dict['TaxVersion']()
    tax_version.kind = line[4]
    tax_version.value = Decimal(line[3])
    tax_version.start_date = datetime.datetime.strptime(line[2], '%d/%m/%Y')
    append_version(tax, tax_version)
    tax.save()
    return tax


def create_objects(cfg_dict, name):
    path = os.path.join(cfg_dict['dir_loc'], name)
    reader = csv.reader(open(path, 'rb'), delimiter=';')
    n = 0
    for cur_line in reader:
        get_or_create_objects(cfg_dict, cur_line)
        n += 1

    print 'Successfully created %s %s' % (n, name)


def launch_test_case(cfg_dict):
    cfg_dict = update_cfg_dict_with_models(cfg_dict)
    create_objects(cfg_dict, 'taxes')
