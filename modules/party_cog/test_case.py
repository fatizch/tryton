# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import random
import datetime
from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache
from trytond.modules.coog_core import fields
from trytond.modules.coog_core import coog_string


MODULE_NAME = 'party_cog'

__all__ = [
    'TestCaseModel',
    'GlobalSearchSet',
    ]


class GlobalSearchSet:
    __metaclass__ = PoolMeta
    __name__ = 'global_search.set'

    @classmethod
    def global_search_list(cls):
        res = super(GlobalSearchSet, cls).global_search_list()
        res.add('party.party')
        return res


class TestCaseModel:
    __metaclass__ = PoolMeta
    __name__ = 'ir.test_case'

    number_of_parties = fields.Integer('Number of Parties')
    number_of_males = fields.Integer('Number of Males')
    adult_age_min = fields.Integer('Minimum age for adults')
    adult_age_max = fields.Integer('Maximum age for adults')
    percent_of_couple = fields.Integer('Percentage of couples')
    max_nb_of_children_per_couple = fields.Integer('Maximum number of children'
        ' per couple')
    percent_of_couple_with_children = fields.Integer('Percentage of couples'
        ' with children')
    percent_of_couple_with_same_name = fields.Integer('Percentage of couples'
        ' with the same name')
    phone_prefix = fields.Char('Phone Prefix')
    _get_country_cache = Cache('get_country')
    _get_country_code_cache = Cache('get_country_by_code')

    @classmethod
    def global_search_list(cls):
        res = super(TestCaseModel, cls).global_search_list()
        res.add('party.party')
        return res

    @classmethod
    def create_relation_type(cls, **kwargs):
        RelationType = Pool().get('party.relation.type')
        return RelationType(**kwargs)

    @classmethod
    def relation_type_test_case_test_method(cls):
        RelationType = Pool().get('party.relation.type')
        return not RelationType.search([('code', '=', 'spouse')])

    @classmethod
    def relation_type_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        spouse = cls.create_relation_type(code='spouse',
            name=translater('Spouse'), reversed_name=translater('Spouse'))
        spouse.save()
        spouse.reverse = spouse
        spouse.save()

        parent = cls.create_relation_type(code='parent',
            name=translater('Parent'))
        parent.save()

        children = cls.create_relation_type(code='children',
            name=translater('Children'), reverse=parent)
        children.save()

        parent.reverse = children
        parent.save()

    @classmethod
    def get_country(cls, country_name):
        result = cls._get_country_cache.get(country_name)
        if result:
            return result
        result = Pool().get('country.country').search([
                ('name', 'ilike', country_name.upper())], limit=1)[0].id
        cls._get_country_cache.set(country_name, result)
        return result

    @classmethod
    def get_country_by_code(cls, country_code):
        result = cls._get_country_code_cache.get(country_code)
        if result:
            return result
        countries = Pool().get('country.country').search([
                ('code', '=', country_code.upper())], limit=1)
        if not countries:
            return None
        result = countries[0].id
        cls._get_country_code_cache.set(country_code, result)
        return result

    @classmethod
    def create_zip_code(cls, **kwargs):
        Zip = Pool().get('country.zip')
        return Zip(**kwargs)

    @classmethod
    def create_relation(cls, **kwargs):
        Relation = Pool().get('party.relation')
        return Relation(**kwargs)

    @classmethod
    def create_zip_code_if_necessary(cls, address):
        if not (address.zip and address.country and address.city):
            return
        Zip = Pool().get('country.zip')
        domain = [
            ('city', '=', address.city),
            ('zip', '=', address.zip),
            ('country', '=', address.country.id)
            ]
        if Zip.search(domain):
            return
        zipcode = cls.create_zip_code(city=address.city,
            country=address.country, zip=address.zip)
        return zipcode

    @classmethod
    def create_address(cls, **kwargs):
        Address = Pool().get('party.address')
        result = Address(**kwargs)
        cls.create_zip_code_if_necessary(result)
        return result

    @classmethod
    def new_address(cls, party_kind):
        files = cls._loaded_resources[MODULE_NAME]['files']
        address = None
        while not address:
            try:
                data = random.choice(files['address_%s.csv' % party_kind])
                # zfill(5) is not country safe
                address = cls.create_address(street='\n'.join(['', '',
                            data['street'], data['streetbis']]),
                    country=cls.get_country(data['country']),
                    zip=data['zip'].zfill(5), city=data['city'])
            except ValueError:
                cls.get_logger().debug('Unable to create address from %s' %
                    str(data))
                pass
        return address

    @classmethod
    def create_contact(cls, **kwargs):
        Contact = Pool().get('party.contact_mechanism')
        return Contact(**kwargs)

    @classmethod
    def create_party(cls, **kwargs):
        Party = Pool().get('party.party')
        if 'is_person' not in kwargs:
            kwargs['is_person'] = False
        party = Party(**kwargs)
        if 'contact_mechanisms' in kwargs:
            return party
        party.contact_mechanisms = []
        Configuration = cls.get_instance()
        possible_domains = ['gmail.com', 'yahoo.com', 'aol.com',
            'hotmail.com']
        for contact_type in ('phone', 'email'):
            contacts = []
            if contact_type == 'email':
                if not party.is_person:
                    if party.commercial_name:
                        suffix = party.commercial_name
                    else:
                        suffix = party.name
                    suffix = coog_string.slugify(suffix, lower=False)
                    value = 'contact@%s.com' % suffix
                elif party.is_person:
                    prefix = ''
                    if party.first_name:
                        prefix = '%s.' % coog_string.slugify(
                            party.first_name, lower=False)
                    prefix += coog_string.slugify(party.name, lower=False)
                    value = '%s@%s' % (prefix, random.choice(
                            possible_domains))
                value = value.replace(' ', '').lower()
            elif contact_type == 'phone':
                value = (Configuration.phone_prefix
                    + str(random.randint(100000000, 999999999)))
            contacts.append(cls.create_contact(
                    type=contact_type, value=value))
        party.contact_mechanisms = contacts
        return party

    @classmethod
    def new_person(cls, sex='male', with_address=True):
        def calculate_date_interval(age_min, age_max):
            start_date = datetime.date.today()
            start_date = start_date.replace(year=start_date.year -
                int(age_max)).toordinal()
            end_date = datetime.date.today()
            end_date = end_date.replace(year=end_date.year -
                int(age_min)).toordinal()
            return [start_date, end_date]

        Configuration = cls.get_instance()
        if sex == 'child':
            sex = random.choice(['male', 'female'])
            date_interval = calculate_date_interval(1,
                Configuration.adult_age_min)
        else:
            date_interval = calculate_date_interval(
                Configuration.adult_age_min, Configuration.adult_age_max)
        files = cls._loaded_resources[MODULE_NAME]['files']
        person = cls.create_party(is_person=True,
            name=random.choice(files['last_name']), gender=sex,
            first_name=random.choice(files[sex]),
            birth_date=datetime.date.fromordinal(
                random.randint(date_interval[0], date_interval[1])),
            addresses=[], lang=cls.get_language(), relations=[])
        if with_address:
            person.addresses = [cls.new_address('person')]
        return person

    @classmethod
    def party_test_case(cls):
        Party = Pool().get('party.party')
        Relation = Pool().get('party.relation')
        RelationType = Pool().get('party.relation.type')
        Configuration = cls.get_instance()
        nb_males = Party.search_count([('is_person', '=', True),
                ('gender', '=', 'male')])
        nb_females = Party.search_count([('is_person', '=', True),
                ('gender', '=', 'female')])
        if nb_males + nb_females < Configuration.number_of_parties:
            total_nb = max(0, Configuration.number_of_parties
                - nb_males - nb_females)
            nb_males = max(0, Configuration.number_of_males - nb_males)
            nb_females = max(0, total_nb - nb_males - nb_females)
        else:
            return
        cls.load_resources(MODULE_NAME)
        cls.read_list_file('male', MODULE_NAME)
        cls.read_list_file('female', MODULE_NAME)
        cls.read_list_file('last_name', MODULE_NAME)
        cls.read_csv_file('address_person.csv', MODULE_NAME, sep=';',
            reader='dict')
        relation_spouse = RelationType.search([('code', '=', 'spouse')])[0]
        relation_parent = RelationType.search([('code', '=', 'parent')])[0]
        persons = []
        relations = []
        i = 0
        while i <= total_nb:
            person1 = cls.new_person('male' if nb_males else 'female')
            persons.append(person1)
            if nb_males > 0:
                nb_males -= 1
            else:
                nb_females -= 1
            i += 1
            if nb_males and cls.launch_dice(Configuration.percent_of_couple):
                person2 = cls.new_person('female', with_address=False)
                persons.append(person2)
                i += 1
                nb_females -= 1
                if cls.launch_dice(
                        Configuration.percent_of_couple_with_same_name):
                    person2.name = person1.name
                relation = cls.create_relation(to=person2,
                    type=relation_spouse, from_=person1)
                relations.append(relation)
                if not cls.launch_dice(
                        Configuration.percent_of_couple_with_children):
                    continue
                for k in range(random.randint(1,
                        Configuration.max_nb_of_children_per_couple)):
                    child = cls.new_person('child', with_address=False)
                    child.name = person1.name
                    persons.append(child)
                    for parent in (person1, person2):
                        relation = cls.create_relation(to=child,
                            type=relation_parent, from_=parent)
                        relations.append(relation)
        new_persons = Party.create([x._save_values for x in persons])
        for person, new_person in zip(persons, new_persons):
            person.id = new_person.id
        Relation.create([x._save_values for x in relations])

    @classmethod
    def new_company(cls, name, commercial_name='', child_level=None,
            cur_depth=None):
        translater = cls.get_translater(MODULE_NAME)
        company = cls.create_party(name=name, commercial_name=commercial_name)
        result = []
        if cur_depth and cur_depth > 0:
            for i in range(1, 3):
                result.append(cls.new_company(
                        '%s %s%s' % (translater('Subsidiary'), child_level, i),
                        '%s%s' % (child_level, i), child_level + 1,
                        cur_depth - 1))
        company.children = result
        return company

    @classmethod
    def hierarchy_test_case(cls):
        company = cls.new_company('Coog', 'Coog', 1, 4)
        company.save()

    @classmethod
    def get_user_group_dict(cls):
        user_group_dict = super(TestCaseModel, cls).get_user_group_dict()
        for user_read in ['consultation', 'claim']:
            user_group_dict[user_read].append('party_cog.group_party_read')
        for user_manage in ['financial', 'product', 'underwriting',
                'commission', 'contract']:
            user_group_dict[user_manage].append('party_cog.group_party_manage')
        return user_group_dict
