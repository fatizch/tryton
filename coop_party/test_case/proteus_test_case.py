#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import date
import random
import os
import csv
from proteus import Model
import proteus_tools


def update_models(cfg_dict):
    cfg_dict['Party'] = Model.get('party.party')
    cfg_dict['RelationKind'] = Model.get('party.party_relation_kind')
    cfg_dict['Relation'] = Model.get('party.party-relation')
    cfg_dict['AddressKind'] = Model.get('party.address_kind')
    cfg_dict['Address'] = Model.get('party.address')
    cfg_dict['Country'] = Model.get('country.country')
    cfg_dict['Language'] = Model.get('ir.lang')
    return cfg_dict


def load_addresses(cfg_dict, party_kind):
    path = os.path.join(cfg_dict['dir_loc'], 'address_' + party_kind + '.csv')
    reader = csv.DictReader(open(path, 'rb'), delimiter=';')
    cfg_dict['address_' + party_kind] = []
    for cur_line in reader:
        cfg_dict['address_' + party_kind].append(cur_line)
    return cfg_dict


def get_country(cfg_dict, name):
    if name == '':
        return None
    if not cfg_dict.get('countries', None):
        cfg_dict['countries'] = {}
    if cfg_dict['countries'].get(name, None):
        return cfg_dict['countries'][name]
    Country = cfg_dict['Country']
    countries = Country.find([('name', 'ilike', name.upper())], limit=1)
    if len(countries) > 0:
        cfg_dict['countries'][name] = countries[0]
        return countries[0]


def create_address(cfg_dict, party, party_kind):
    data = random.choice(cfg_dict['address_' + party_kind])
    try:
        res = cfg_dict['Address']()
        res.party = party
        res.street = data['street']
        res.streetbis = data['streetbis']
        res.country = get_country(cfg_dict, data['country'])
        res.zip = data['zip'].zfill(5)
        res.city = data['city']
        proteus_tools.create_zip_code_if_necessary(res)
        res.save()
        return res
    except:
        print 'Impossible to store address % s' % res
        print data
        return None


def create_persons(cfg_dict, nb_male, nb_female, relations_kind,
        addresses_kind):
    dicts = {}
    path = cfg_dict['dir_loc']
    dicts['male'] = get_name_as_liste(
        os.path.join(path, 'male'), nb_male)
    dicts['female'] = get_name_as_liste(
        os.path.join(path, 'female'), nb_female)
    dicts['last_name'] = get_name_as_liste(
        os.path.join(path, 'last_name'), nb_male + nb_female)
    adult_date_interv = calculate_date_interval(cfg_dict,
        cfg_dict['adult_age_min'], cfg_dict['adult_age_max'])
    children_date_interv = calculate_date_interval(cfg_dict, 1, 18)
    cfg_dict = load_addresses(cfg_dict, 'person')

    for _i in range(nb_male):
        name = random.choice(dicts['last_name'])
        person1 = add_person(cfg_dict, name, dicts, adult_date_interv, 'male')
        while not create_address(cfg_dict, person1, 'person'):
            print 'Erreur in address, retrying'
        if launch_dice(cfg_dict, 'percent_of_couple'):
            if not launch_dice(cfg_dict, 'percent_of_couple_with_same_name'):
                name = random.choice(dicts['last_name'])
            person2 = add_person(cfg_dict, name, dicts, adult_date_interv,
                'female')
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
        add_person(cfg_dict, name, dicts, adult_date_interv, 'female')

    print 'Successfully created %s parties' % (nb_male + nb_female)


def create_relation(cfg_dict, from_actor, to_actor, kind, start_date=None):
    relation = cfg_dict['Relation']()
    relation.from_party = from_actor
    relation.to_party = to_actor
    relation.kind = kind
    if start_date:
        relation.start_date = start_date
    relation.save()


def launch_dice(cfg_dict, probability_name):
    return random.randint(0, 99) < int(cfg_dict[probability_name])


def calculate_date_interval(cfg_dict, age_min, age_max):
    start_date = date.today()
    start_date = start_date.replace(year=start_date.year
        - int(age_max)).toordinal()
    end_date = date.today()
    end_date = end_date.replace(year=end_date.year
        - int(age_min)).toordinal()
    return [start_date, end_date]


def get_language(cfg_dict, code):
    if not 'languages' in cfg_dict:
        cfg_dict['languages'] = {}
    if not code in cfg_dict['languages']:
        lang = proteus_tools.get_objects_from_db(cfg_dict, 'Language', 'code',
            code)
        if lang:
            cfg_dict['languages'][code] = lang
        else:
            return
    return cfg_dict['languages'][code]


def add_person(cfg_dict, name, dicts, date_interv, sex=None):
    person = cfg_dict['Party']()
    person.is_person = True
    person.name = name
    if not sex:
        sex = random.choice(['male', 'female'])
    person.gender = sex
    person.first_name = random.choice(dicts[person.gender])
    person.birth_date = date.fromordinal(
        random.randint(date_interv[0], date_interv[1]))
    person.addresses[:] = []
    person.lang = get_language(cfg_dict, cfg_dict['language'])
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


def create_parties(cfg_dict):
    relations_kind = get_relations_kind(cfg_dict)
    addresses_kind = create_address_kind(cfg_dict)
    nb_male = 0
    nb_female = 0
    for person in proteus_tools.get_objects_from_db(cfg_dict, 'Party',
            limit=None, domain=[('is_person', '=', True)]):
        if person.gender == 'male':
            nb_male += 1
        if person.gender == 'female':
            nb_female += 1
    if nb_male + nb_female < int(cfg_dict['total_nb']):
        total_nb = max(0, int(cfg_dict['total_nb']) - nb_male - nb_female)
        nb_male = max(0, int(cfg_dict['nb_male']) - nb_male)
        nb_female = max(0, total_nb - nb_male - nb_female)
        create_persons(cfg_dict, nb_male, nb_female, relations_kind,
            addresses_kind)


def create_company(cfg_dict, name, short_name=None, parent=None,
        children_level=None, children_depth=None):
    res = cfg_dict['Party']()
    res.is_company = True
    res.name = name
    res.short_name = short_name
    if parent:
        res.parent = parent
    res.save()
    if children_depth and children_depth > 0:
        for i in range(1, 3):
            create_company(cfg_dict,
                'subsidiary %s%s' % (children_level, i),
                '%s%s' % (children_level, i), res, children_level + 1,
                children_depth - 1)
    return res


def create_hierarchy(cfg_dict):
    if proteus_tools.get_objects_from_db(cfg_dict, 'Party', key='name',
            value='Mother House'):
        return
    create_company(cfg_dict, 'Mother House', 'MH', None, 1, 4)


def launch_test_case(cfg_dict):
    update_models(cfg_dict)
    create_parties(cfg_dict)
    create_hierarchy(cfg_dict)
