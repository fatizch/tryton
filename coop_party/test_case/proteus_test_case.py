#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date
import ConfigParser
import random
import os
from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def setup():
    res = {}
    res['Person'] = Model.get('party.person')
    return res


def get_template_file_path():
    config = ConfigParser.ConfigParser()
    config.read(os.path.abspath(os.path.join(
                DIR, '..', '..', 'coop_utils/coop.cfg')))
    return os.path.join(DIR, config.get('localization', 'country').lower())


def launch_test_case():
    models = setup()
    config = ConfigParser.ConfigParser()
    config.read(os.path.join(DIR, 'test_case.cfg'))
    dicts = {}
    total_nb = config.getint('test_case', 'total_nb')
    nb_male = config.getint('test_case', 'nb_male')
    nb_female = total_nb - nb_male
    path = get_template_file_path()
    dicts['male'] = get_dictionnary(
        os.path.join(path, 'male.txt'), nb_male)
    dicts['female'] = get_dictionnary(
        os.path.join(path, 'female.txt'), nb_female)
    dicts['last_name'] = get_dictionnary(
        os.path.join(path, 'last_name.txt'), total_nb)
    date_interv = calculate_date_interval(config)

    for i in range(nb_male):
        add_person(models, dicts, date_interv, 'M', i)

    for j in range(nb_female):
        add_person(models, dicts, date_interv, 'F', i + j + 1)


def calculate_date_interval(config):
    start_date = date.today()
    start_date = start_date.replace(year=start_date.year
        - config.getint('test_case', 'adult_age_max')).toordinal()
    end_date = date.today()
    end_date = end_date.replace(year=end_date.year
        - config.getint('test_case', 'adult_age_min')).toordinal()
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
    person.save()


def get_dictionnary(file_name, size):
    fd = open(file_name, 'r')
    res = {}
    n = 0
    for line in fd:
        res[n] = line.strip()
        n += 1
        #item are ordered by name popularity, if the sample is small,
        #no need to search for too exotic name
        if n >= 4 * size:
            break
    fd.close()
    return res


def get_random(the_dict):
    return u'%s' % the_dict.get(random.randint(0, len(the_dict) - 1))


if __name__ == '__main__':
    launch_test_case()
