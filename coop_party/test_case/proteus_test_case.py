#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date
import random
import os
import csv
from proteus import Model

DIR = os.path.abspath(os.path.join(os.path.normpath(__file__), '..'))


def update_models(cfg_dict):
    cfg_dict['Person'] = Model.get('party.person')
    cfg_dict['RelationKind'] = Model.get('party.party_relation_kind')
    cfg_dict['Relation'] = Model.get('party.party-relation')
    cfg_dict['AddressKind'] = Model.get('party.address_kind')
    cfg_dict['Address'] = Model.get('party.address')
    cfg_dict['Country'] = Model.get('country.country')
    return cfg_dict


def load_addresses(cfg_dict, party_kind):
    path = os.path.join(DIR, cfg_dict.get('language', 'fr')[0:2].lower(),
        'address_' + party_kind + '.csv')
    reader = csv.DictReader(open(path, 'rb'), delimiter=';')
    cfg_dict['address_' + party_kind] = []
    for cur_line in reader:
        cfg_dict['address_' + party_kind].append(cur_line)
    return cfg_dict


def get_country(cfg_dict, name):
    if name == '':
        return cfg_dict, None
    if not cfg_dict.get('countries', None):
        cfg_dict['countries'] = {}
    if cfg_dict['countries'].get(name, None):
        return cfg_dict, cfg_dict['countries'][name]
    Country = cfg_dict['Country']
    countries = Country.find([('name', 'ilike', name.upper())], limit=1)
    if len(countries) > 0:
        cfg_dict['countries'][name] = countries[0]
        return cfg_dict, countries[0]


def create_address(cfg_dict, party, party_kind):
    res = cfg_dict['Address']()
    res.party = party
    data = random.choice(cfg_dict['address_' + party_kind])
    res.street = data['street']
    res.streetbis = data['streetbis']
    res.zip = data['zip'].zfill(5)
    res.city = data['city']
    cfg_dict, res.country = get_country(cfg_dict, data['country'])
    try:
        res.save()
        return res
    except:
        print 'Impossible to store address % s' % res
        return None


def create_persons(cfg_dict, relations_kind, addresses_kind):
    dicts = {}
    total_nb = int(cfg_dict['total_nb'])
    nb_male = int(cfg_dict['nb_male'])
    nb_female = total_nb - nb_male
    path = os.path.join(DIR, cfg_dict.get('language', 'fr')[0:2].lower())
    dicts['male'] = get_name_as_liste(
        os.path.join(path, 'male'), nb_male)
    dicts['female'] = get_name_as_liste(
        os.path.join(path, 'female'), nb_female)
    dicts['last_name'] = get_name_as_liste(
        os.path.join(path, 'last_name'), total_nb)
    adult_date_interv = calculate_date_interval(cfg_dict,
        cfg_dict['adult_age_min'], cfg_dict['adult_age_max'])
    children_date_interv = calculate_date_interval(cfg_dict, 1, 18)
    cfg_dict = load_addresses(cfg_dict, 'person')

    for _i in range(nb_male):
        name = random.choice(dicts['last_name'])
        person1 = add_person(cfg_dict, name, dicts, adult_date_interv, 'M')
        while not create_address(cfg_dict, person1.party, 'person'):
            print 'Erreur in address, retrying'
        if launch_dice(cfg_dict, 'percent_of_couple'):
            if not launch_dice(cfg_dict, 'percent_of_couple_with_same_name'):
                name = random.choice(dicts['last_name'])
            person2 = add_person(cfg_dict, name, dicts, adult_date_interv, 'F')
            nb_female -= 1
            create_relation(cfg_dict, person1, person2,
                relations_kind['spouse'].key)
            if launch_dice(cfg_dict, 'percent_of_couple_with_children'):
                for _k in range(random.randint(1,
                        int(cfg_dict['max_nb_of_children_per_couple']))):
                    children = add_person(cfg_dict, person1.name,
                        dicts, children_date_interv)
                    create_relation(cfg_dict, person1, children,
                        relations_kind['parent'].key, children.birth_date)

    for _j in range(nb_female):
        name = random.choice(dicts['last_name'])
        add_person(cfg_dict, name, dicts, adult_date_interv, 'F')

    print 'Successfully created %s parties' % total_nb


def create_relation(cfg_dict, from_actor, to_actor, kind, start_date=None):
    relation = cfg_dict['Relation']()
    relation.from_party = from_actor.party
    relation.to_party = to_actor.party
    relation.kind = kind
    if start_date:
        relation.start_date = start_date
    relation.save()


def launch_dice(cfg_dict, probability_name):
    return random.randint(0, 99) < int(cfg_dict[probability_name])


def launch_test_case(cfg_dict):
    cfg_dict = update_models(cfg_dict)
    relations_kind = get_relations_kind(cfg_dict)
    addresses_kind = create_address_kind(cfg_dict)
    if is_table_empty(cfg_dict['Person']):
        create_persons(cfg_dict, relations_kind, addresses_kind)


def calculate_date_interval(cfg_dict, age_min, age_max):
    start_date = date.today()
    start_date = start_date.replace(year=start_date.year
        - int(age_max)).toordinal()
    end_date = date.today()
    end_date = end_date.replace(year=end_date.year
        - int(age_min)).toordinal()
    return [start_date, end_date]


def add_person(cfg_dict, name, dicts, date_interv, sex=None):
    person = cfg_dict['Person']()
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


def get_relation_kind(cfg_dict, key):
    res = cfg_dict['RelationKind'].find([('key', '=', key)])
    if len(res) > 0:
        return res[0]


def get_relations_kind(cfg_dict):
    res = {}
    res['spouse'] = get_relation_kind(cfg_dict, 'spouse')
    res['parent'] = get_relation_kind(cfg_dict, 'parent')
    return res


def get_address_kind(cfg_dict, key):
    res = cfg_dict['AddressKind'].find([('key', '=', key)])
    if len(res) > 0:
        return res[0]


def create_address_kind(cfg_dict):
    res = {}
    res['main'] = get_address_kind(cfg_dict, 'main')
    res['2nd'] = get_address_kind(cfg_dict, '2nd')
    res['job'] = get_address_kind(cfg_dict, 'job')
    return res
