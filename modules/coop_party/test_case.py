import random
import datetime
from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache
from trytond.modules.coop_utils import set_test_case, fields, coop_date
from trytond.modules.coop_utils import coop_string


MODULE_NAME = 'coop_party'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

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
    @set_test_case('Relation Kind Test Case')
    def relation_kind_test_case(cls):
        RelationKind = Pool().get('party.party_relation_kind')
        spouse = RelationKind()
        spouse.code = 'spouse'
        spouse.name = cls.translate_this('Spouse', MODULE_NAME)
        spouse.reversed_name = cls.translate_this('Spouse', MODULE_NAME)
        parent = RelationKind()
        parent.code = 'parent'
        parent.name = cls.translate_this('Parent', MODULE_NAME)
        parent.reversed_name = cls.translate_this('Children', MODULE_NAME)
        return [spouse, parent]

    @classmethod
    @set_test_case('Address Kind Test Case')
    def address_kind_test_case(cls):
        AddressKind = Pool().get('party.address_kind')
        main = AddressKind()
        main.key = 'main'
        main.name = cls.translate_this('Main', MODULE_NAME)
        second = AddressKind()
        second.key = '2nd'
        second.name = cls.translate_this('Secondary', MODULE_NAME)
        job = AddressKind()
        job.key = 'job'
        job.name = cls.translate_this('Job', MODULE_NAME)
        return [main, second, job]

    @classmethod
    def create_person(cls, sex='male'):
        Party = Pool().get('party.party')
        Configuration = cls.get_instance()
        if sex == 'child':
            sex = random.choice(['male', 'female'])
            date_interval = coop_date.calculate_date_interval(1,
                Configuration.adult_age_min)
        else:
            date_interval = coop_date.calculate_date_interval(
                Configuration.adult_age_min, Configuration.adult_age_max)
        files = cls._loaded_resources[MODULE_NAME]['files']
        person = Party()
        person.is_person = True
        person.name = random.choice(files['last_name'])
        person.gender = sex
        person.first_name = random.choice(files[sex])
        person.birth_date = datetime.date.fromordinal(
            random.randint(date_interval[0], date_interval[1]))
        person.addresses = []
        person.lang = cls.get_language()
        person.relations = []
        return person

    @classmethod
    def get_country(cls, country_name):
        result = cls._get_country_cache.get(country_name)
        if result:
            return result
        result = Pool().get('country.country').search([
                ('name', 'ilike', country_name.upper())], limit=1)[0]
        cls._get_country_cache.set(country_name, result)
        return result

    @classmethod
    def get_country_by_code(cls, country_code):
        result = cls._get_country_code_cache.get(country_code)
        if result:
            return result
        result = Pool().get('country.country').search([
                ('code', '=', country_code.upper())], limit=1)[0]
        cls._get_country_code_cache.set(country_code, result)
        return result

    @classmethod
    def create_zip_code_if_necessary(cls, address):
        if not (address.zip and address.country and address.city):
            return
        Zip = Pool().get('country.zipcode')
        domain = [
            ('city', '=', address.city),
            ('zip', '=', address.zip),
            ('country', '=', address.country.id)
        ]
        if Zip.search(domain):
            return
        zipcode = Zip()
        zipcode.city = address.city
        zipcode.country = address.country
        zipcode.zip = address.zip
        zipcode.save()
        return zipcode

    @classmethod
    def create_address(cls, party, party_kind=''):
        Address = Pool().get('party.address')
        files = cls._loaded_resources[MODULE_NAME]['files']
        if not party_kind and party.is_person:
            party_kind = 'person'
        address = None
        while not address:
            try:
                data = random.choice(files['address_%s.csv' % party_kind])
                address = Address()
                address.street = data['street']
                address.streetbis = data['streetbis']
                address.country = cls.get_country(data['country'])
                # zfill(5) is not country safe
                address.zip = data['zip'].zfill(5)
                address.city = data['city']
                cls.create_zip_code_if_necessary(address)
                party.addresses.append(address)
            except:
                cls.get_logger().debug('Unable to create address from %s' %
                    str(data))
                pass
        return address

    @classmethod
    @set_test_case('Party Test Case', 'relation_kind_test_case',
        'address_kind_test_case')
    def party_test_case(cls):
        Party = Pool().get('party.party')
        PartyRelation = Pool().get('party.party-relation')
        RelationKind = Pool().get('party.party_relation_kind')
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
        relation_spouse = RelationKind.search([('code', '=', 'spouse')])[0]
        relation_child = RelationKind.search([('code', '=', 'parent')])[0]
        persons = []
        i = 0
        while i <= total_nb:
            person1 = cls.create_person('male' if nb_males else 'female')
            persons.append(person1)
            if nb_males > 0:
                nb_males -= 1
            else:
                nb_females -= 1
            i += 1
            cls.create_address(person1)
            if nb_males and cls.launch_dice(Configuration.percent_of_couple):
                person2 = cls.create_person('female')
                persons.append(person2)
                i += 1
                nb_females -= 1
                if cls.launch_dice(
                        Configuration.percent_of_couple_with_same_name):
                    person2.name = person1.name
                relation = PartyRelation()
                relation.to_party = person2
                relation.relation_kind = relation_spouse
                person1.relations.append(relation)
                if not cls.launch_dice(
                        Configuration.percent_of_couple_with_children):
                    continue
                for k in range(random.randint(1,
                        Configuration.max_nb_of_children_per_couple)):
                    child = cls.create_person('child')
                    child.name = person1.name
                    persons.append(child)
                    for parent in (person1, person2):
                        relation = PartyRelation()
                        relation.to_party = child
                        relation.relation_kind = relation_child
                        parent.relations.append(relation)
        return persons

    @classmethod
    def create_company(cls, name, short_name='', child_level=None,
            cur_depth=None):
        company = Pool().get('party.party')()
        company.is_company = True
        company.name = name
        company.short_name = short_name
        result = []
        if cur_depth and cur_depth > 0:
            for i in range(1, 3):
                result += cls.create_company(
                    '%s %s%s' % (cls.translate_this('Subsidiary', MODULE_NAME),
                        child_level, i),
                    '%s%s' % (child_level, i), child_level + 1, cur_depth - 1)
        company.children = result
        return [company]

    @classmethod
    @set_test_case('Hierarchy Test Case')
    def hierarchy_test_case(cls):
        return cls.create_company('Coop', 'Coop', 1, 4)

    @classmethod
    @set_test_case('Contact Mechanism Test Case', 'party_test_case')
    def contact_mechanism_test_case(cls):
        pool = Pool()
        Party = pool.get('party.party')
        Contact = pool.get('party.contact_mechanism')
        Configuration = pool.get('coop_utils.test_case_model').get_instance()
        possible_domains = ['gmail.com', 'yahoo.com', 'aol.com',
            'hotmail.com']
        result = []
        for party in Party.search([('contact_mechanisms', '=', None)]):
            for contact_type in ('phone', 'email'):
                contact = Contact()
                contact.party = party
                contact.type = contact_type
                if contact_type == 'email':
                    if party.is_company:
                        if party.short_name:
                            suffix = party.short_name
                        else:
                            suffix = party.name
                        suffix = coop_string.remove_invalid_char(suffix)
                        contact.value = 'contact@%s.com' % suffix
                    elif party.is_person:
                        prefix = ''
                        if party.first_name:
                            prefix = '%s.' % coop_string.remove_invalid_char(
                                party.first_name)
                        prefix += coop_string.remove_invalid_char(party.name)
                        contact.value = '%s@%s' % (prefix, random.choice(
                                possible_domains))
                    contact.value = contact.value.replace(' ', '').lower()
                elif contact_type == 'phone':
                    contact.value = (Configuration.phone_prefix
                        + str(random.randint(100000000, 999999999)))
                result.append(contact)
        return result
