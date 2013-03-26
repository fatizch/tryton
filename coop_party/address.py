#-*- coding:utf-8 -*-
import copy

from trytond.pool import Pool, PoolMeta
from trytond.modules.coop_utils import DynamicSelection, utils
from trytond.modules.coop_utils import coop_string, business, fields

__all__ = ['Address', 'AddresseKind']


class Address():
    "Address"

    __metaclass__ = PoolMeta

    __name__ = 'party.address'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    kind = fields.Selection('get_possible_address_kind', 'Kind')
    zip_and_city = fields.Function(fields.Many2One('country.zipcode', 'Zip',
            on_change=['zip', 'country', 'city', 'zip_and_city']),
        'get_zip_and_city', 'set_zip_and_city')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls.city = copy.copy(cls.city)
        if not cls.city.on_change_with:
            cls.city.on_change_with = []
        utils.extend_inexisting(cls.city.on_change_with,
            ['zip', 'country', 'city'])
        if not cls.city.autocomplete:
            cls.city.autocomplete = []
        utils.extend_inexisting(cls.city.autocomplete,
            ['zip', 'country'])

        cls.zip = copy.copy(cls.zip)
        if not cls.zip.on_change_with:
            cls.zip.on_change_with = []
        utils.extend_inexisting(cls.zip.on_change_with,
            ['zip', 'country', 'city'])
        if not cls.zip.autocomplete:
            cls.zip.autocomplete = []
        utils.extend_inexisting(cls.zip.autocomplete,
            ['city', 'country'])

        cls.city = copy.copy(cls.city)
        if not cls.city.states:
            cls.city.states = {}
        cls.city.states['invisible'] = True
        cls.zip = copy.copy(cls.zip)
        if not cls.zip.states:
            cls.zip.states = {}
        cls.zip.states['invisible'] = True

    @classmethod
    def get_summary(cls, addresses, name=None, at_date=None, lang=None):
        res = {}
        for address in addresses:
            res[address.id] = ''
            indent = 0
            if address.kind:
                res[address.id] = coop_string.get_field_as_summary(address,
                    'kind', False, at_date, lang=lang)
                indent = 1
            res[address.id] += coop_string.re_indent_text(
                address.get_full_address(name), indent)
        return res

    @staticmethod
    def default_start_date():
        return utils.today()

    @classmethod
    def get_possible_address_kind(cls, vals=None):
        return AddresseKind.get_values_as_selection('party.address_kind')

    @staticmethod
    def default_kind():
        'RSE TODO : what if this address kind was removed or modified?'
        return 'main'

    @staticmethod
    def get_cities_from_zip(zipcode, country):
        domain = []
        domain.append(('zip', '=', zipcode))
        domain.append(('country', '=', country))
        return utils.get_those_objects('country.zipcode', domain)

    @staticmethod
    def get_zips_from_city(city, country):
        domain = []
        domain.append(('city', '=', city))
        domain.append(('country', '=', country))
        return utils.get_those_objects('country.zipcode', domain)

    def on_change_with_city(self):
        if self.zip and self.country:
            cities = self.get_cities_from_zip(self.zip, self.country)
            if cities:
                return cities[0].city
            else:
                return self.city

    def on_change_with_zip(self):
        if self.city and self.country:
            zips = self.get_zips_from_city(self.city, self.country)
            if zips:
                return zips[0].zip
            else:
                return self.zip

#    @classmethod
#    def create(cls, vals):
#        address = super(Address, cls).create(vals)
#        if not all([elem in vals for elem in ['zip', 'country', 'city']]):
#            return address
#        ZipCode = Pool().get('country.zipcode')
#        if len(ZipCode.search(
#                [
#                    ('zip', '=', vals['zip']),
#                    ('country', '=', vals['country']),
#                ])) > 0:
#            return address
#        ZipCode.create(
#            {
#                'zip': vals['zip'],
#                'city': vals['city'],
#                'country': vals['country']
#            })
#        return address

    @staticmethod
    def default_country():
        return business.get_default_country()

    def autocomplete_city(self):
        if self.zip and self.country:
            cities = self.get_cities_from_zip(self.zip, self.country)
            return [x.city for x in cities]
        else:
            return ['']

    def autocomplete_zip(self):
        if self.city and self.country:
            zips = self.get_zips_from_city(self.city, self.country)
            return [x.zip for x in zips]
        else:
            return ['']

    def get_zip_and_city(self, name):
        Zip = Pool().get('country.zipcode')
        domain = [
            ('city', '=', self.city),
            ('zip', '=', self.zip),
        ]
        if self.country:
            domain.append(('country', '=', self.country.id))
        zips = Zip.search(domain, limit=1)
        if zips:
            return zips[0].id

    def on_change_zip_and_city(self):
        res = {'city': '', 'zip': ''}
        if self.zip_and_city:
            res['city'] = self.zip_and_city.city
            res['zip'] = self.zip_and_city.zip
        return res

    @classmethod
    def set_zip_and_city(cls, addresses, name, vals):
        pass

    def get_address_as_char(self, name, with_return_carriage=False):
        full_address = ''
        if self.street:
            if full_address:
                full_address += '\n'
            full_address += self.street
        if self.streetbis:
            if full_address:
                full_address += '\n'
            full_address += self.streetbis
        if self.zip or self.city:
            if full_address:
                full_address += '\n'
            if self.zip:
                full_address += self.zip
            if self.city:
                if full_address[-1:] != '\n':
                    full_address += ' '
                full_address += self.city
        if self.country or self.subdivision:
            if full_address:
                full_address += '\n'
            if self.subdivision:
                full_address += self.subdivision.name
            if self.country:
                if full_address[-1:] != '\n':
                    full_address += ' '
                full_address += self.country.name
        if not with_return_carriage:
            full_address = full_address.replace('\n', ' ')
        return full_address


class AddresseKind(DynamicSelection):
    'Addresse Kind'

    __name__ = 'party.address_kind'
    _table = 'coop_table_of_table'

    @staticmethod
    def get_class_where_used():
        return [('party.address', 'kind')]
