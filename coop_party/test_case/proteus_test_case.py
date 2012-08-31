#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date
import random
import os
from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def get_models():
    res = {}
    res['Person'] = Model.get('party.person')
    res['RelationKind'] = Model.get('party.party_relation_kind')
    res['Relation'] = Model.get('party.party-relation')
    return res


def create_persons(models, cfg_dict, relations_kind):
    dicts = {}
    total_nb = int(cfg_dict['total_nb'])
    nb_male = int(cfg_dict['nb_male'])
    nb_female = total_nb - nb_male
    path = os.path.join(DIR, cfg_dict.get('language', 'fr')[0:2].lower())
    dicts['male'] = get_name_as_liste(
        os.path.join(path, 'male.txt'), nb_male)
    dicts['female'] = get_name_as_liste(
        os.path.join(path, 'female.txt'), nb_female)
    dicts['last_name'] = get_name_as_liste(
        os.path.join(path, 'last_name.txt'), total_nb)
    adult_date_interv = calculate_date_interval(cfg_dict,
        cfg_dict['adult_age_min'], cfg_dict['adult_age_max'])
    children_date_interv = calculate_date_interval(cfg_dict, 1, 18)

    for _i in range(nb_male):
        name = random.choice(dicts['last_name'])
        person1 = add_person(models, name, dicts, adult_date_interv, 'M')
        if launch_dice(cfg_dict, 'percent_of_couple'):
            if not launch_dice(cfg_dict, 'percent_of_couple_with_same_name'):
                name = random.choice(dicts['last_name'])
            person2 = add_person(models, name, dicts, adult_date_interv, 'F')
            nb_female -= 1
            create_relation(models, person1, person2,
                relations_kind['spouse'].key)
            if launch_dice(cfg_dict, 'percent_of_couple_with_children'):
                for _k in range(random.randint(1,
                        int(cfg_dict['max_nb_of_children_per_couple']))):
                    children = add_person(models, person1.name,
                        dicts, children_date_interv)
                    create_relation(models, person1, children,
                        relations_kind['parent'].key, children.birth_date)

    for _j in range(nb_female):
        name = random.choice(dicts['last_name'])
        add_person(models, name, dicts, adult_date_interv, 'F')

    print 'Successfully created %s parties' % total_nb


def create_relation(models, from_party, to_party, kind, start_date=None):
    relation = models['Relation']()
    relation.from_party = from_party
    relation.to_party = to_party
    relation.kind = kind
    if start_date:
        relation.start_date = start_date
    relation.save()


def launch_dice(cfg_dict, probability_name):
    return random.randint(0, 99) < int(cfg_dict[probability_name])


def launch_test_case(cfg_dict):
    models = get_models()
    relations_kind = create_relations_kind(models)
#    if is_table_empty(models['Person']):
    create_persons(models, cfg_dict, relations_kind)


def calculate_date_interval(cfg_dict, age_min, age_max):
    start_date = date.today()
    start_date = start_date.replace(year=start_date.year
        - int(age_max)).toordinal()
    end_date = date.today()
    end_date = end_date.replace(year=end_date.year
        - int(age_min)).toordinal()
    return [start_date, end_date]


def add_person(models, name, dicts, date_interv, sex=None):
    person = models['Person']()
    person.name = name
    if not sex:
        sex = random.choice(['M', 'F'])
    person.gender = sex
    if sex == 'M':
        the_dict = 'male'
    elif sex == 'F':
        the_dict = 'female'
    person.first_name = random.choice(dicts[the_dict])
    person.birth_date = date.fromordinal(
        random.randint(date_interv[0], date_interv[1]))
    person.addresses[:] = []
    person.save()
    return person


def get_name_as_liste(file_name, size):
    fd = open(file_name, 'r')
    res = []
    n = 0
    for line in fd:
        res.append(line.decode('utf8').strip())
        n += 1
        #item are ordered by name popularity, if the sample is small,
        #no need to search for too exotic name
        if n >= 4 * size:
            break
    fd.close()
    return res


def is_table_empty(model):
    return len(model.find(limit=1)) == 0


def get_or_create_relation_kind(models, key, name, children=None):
    res = models['RelationKind'].find([('key', '=', key)])
    if len(res) > 0:
        return res[0]
    res = models['RelationKind']()
    res.key = key
    res.name = name
    if children:
        res.childs[:] = children
    res.save()
    return res


def create_relations_kind(models):
    res = {}
    res['spouse'] = get_or_create_relation_kind(models, 'spouse', 'Spouse Of')
    res['parent'] = get_or_create_relation_kind(models, 'parent', 'Parent Of',
        [get_or_create_relation_kind(models, 'child', 'Children Of')])
    return res
