import os
import csv
import logging

from proteus import Model


def update_cfg(cfg_dict):
    cfg_dict['Insurer'] = Model.get('party.insurer')
    cfg_dict['Party'] = Model.get('party.party')


def get_or_create_insurer(cfg_dict, code, name):
    insurers = cfg_dict['Party'].find(
        [
            ('name', '=', name),
            ('insurer_role', '>', 0),
        ])
    if insurers:
        return insurers[0]
    insurer = cfg_dict['Insurer']()
    company = cfg_dict['Party']()
    company.is_company = True
    company.insurer_role.append(insurer)
    company.name = name
    company.code = code
    company.addresses[:] = []
    company.currency = cfg_dict['currency']
    company.save()
    return insurer


def create_insurers(cfg_dict):
    path = os.path.join(cfg_dict['dir_loc'], 'insurer')
    reader = csv.reader(open(path, 'rb'), delimiter=';')
    n = 0
    for insurer in reader:
        get_or_create_insurer(cfg_dict, insurer[0], insurer[1])
        n += 1
    logging.getLogger('test_case').info(
        'Successfully created %s insurers' % n)


def launch_test_case(cfg_dict):
    update_cfg(cfg_dict)
    create_insurers(cfg_dict)
