#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date
import random
import os
import warnings
from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def get_models():
    res = {}
    res['Person'] = Model.get('party.person')
    return res


def create_persons(models, cfg_dict):
    dicts = {}
    total_nb = int(cfg_dict['total_nb'])
    nb_male = int(cfg_dict['nb_male'])
    nb_female = total_nb - nb_male
    path = os.path.join(DIR, cfg_dict.get('language', 'fr')[0:2].lower())
    dicts['male'] = get_dictionnary(
        os.path.join(path, 'male.txt'), nb_male)
    dicts['female'] = get_dictionnary(
        os.path.join(path, 'female.txt'), nb_female)
    dicts['last_name'] = get_dictionnary(
        os.path.join(path, 'last_name.txt'), total_nb)
    date_interv = calculate_date_interval(cfg_dict)

    for i in range(nb_male):
        add_person(models, dicts, date_interv, 'M', i)

    for j in range(nb_female):
        add_person(models, dicts, date_interv, 'F', i + j + 1)

    print 'Successfully created %s parties' % total_nb


def launch_test_case(cfg_dict):
    models = get_models()
    if is_table_empty(models['Person']):
        create_persons(models, cfg_dict)


def calculate_date_interval(cfg_dict):
    start_date = date.today()
    start_date = start_date.replace(year=start_date.year
        - int(cfg_dict['adult_age_max'])).toordinal()
    end_date = date.today()
    end_date = end_date.replace(year=end_date.year
        - int(cfg_dict['adult_age_min'])).toordinal()
    return [start_date, end_date]


def add_person(models, dicts, date_interv, sex='M', i=0):
    person = models['Person']()
    person.name = get_random(dicts['last_name'])
    person.gender = sex
    if sex == 'M':
        the_dict = 'male'
    elif sex == 'F':
        the_dict = 'female'
    person.first_name = get_random(dicts[the_dict])
    person.birth_date = date.fromordinal(
        random.randint(date_interv[0], date_interv[1]))
    person.addresses[:] = []
    person.save()


def get_dictionnary(file_name, size):
    fd = open(file_name, 'r')
    res = {}
    n = 0
    for line in fd:
        res[n] = line.decode('utf8').strip()
        n += 1
        #item are ordered by name popularity, if the sample is small,
        #no need to search for too exotic name
        if n >= 4 * size:
            break
    fd.close()
    return res


def get_random(the_dict):
    return u'%s' % the_dict.get(random.randint(0, len(the_dict) - 1))


def is_table_empty(model):
    return len(model.find(limit=1)) == 0
