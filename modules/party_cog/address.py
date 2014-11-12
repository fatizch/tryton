# -*- coding:utf-8 -*-
from trytond.pool import Pool, PoolMeta
from trytond.modules.cog_utils import utils
from trytond.modules.cog_utils import coop_string, fields, export
from trytond.modules.country_cog import country

__metaclass__ = PoolMeta
__all__ = [
    'Address',
    ]


class Address(export.ExportImportMixin):
    __name__ = 'party.address'
    _func_key = 'func_key'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    zip_and_city = fields.Function(
        fields.Many2One('country.zipcode', 'Zip'),
        'get_zip_and_city', 'set_zip_and_city')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        if not cls.city.on_change_with:
            cls.city.on_change_with = []
        utils.extend_inexisting(cls.city.on_change_with,
            ['zip', 'country', 'city'])
        if not cls.city.autocomplete:
            cls.city.autocomplete = []
        utils.extend_inexisting(cls.city.autocomplete,
            ['zip', 'country'])

        if not cls.zip.on_change_with:
            cls.zip.on_change_with = []
        utils.extend_inexisting(cls.zip.on_change_with,
            ['zip', 'country', 'city'])
        if not cls.zip.autocomplete:
            cls.zip.autocomplete = []
        utils.extend_inexisting(cls.zip.autocomplete,
            ['city', 'country'])

        if not cls.city.states:
            cls.city.states = {}
        cls.city.states['invisible'] = True
        if not cls.zip.states:
            cls.zip.states = {}
        cls.zip.states['invisible'] = True

    @classmethod
    def _export_light(cls):
        return set(['country'])

    @classmethod
    def get_summary(cls, addresses, name=None, at_date=None, lang=None):
        res = {}
        for address in addresses:
            res[address.id] = ''
            indent = 0
            res[address.id] += coop_string.re_indent_text(
                address.get_full_address(name), indent)
        return res

    @staticmethod
    def default_start_date():
        return utils.today()

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

    @classmethod
    def _export_keys(cls):
        return set(('party.name', 'street', 'zip', 'city', 'country.code'))

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

    @fields.depends('zip', 'country', 'city', 'zip_and_city')
    def on_change_zip_and_city(self):
        self.city = self.zip_and_city.city if self.zip_and_city else ''
        self.zip = self.zip_and_city.zip if self.zip_and_city else ''

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

    @classmethod
    def get_var_names_for_full_extract(cls):
        return['street', 'streetbis', 'zip', 'city', ('country', 'light')]

    def get_rec_name(self, name):
        return self.get_address_as_char(name)

    @staticmethod
    def default_country():
        return country.Country.default_country().id

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('street',) + tuple(clause[1:])],
            [('city',) + tuple(clause[1:])],
            [('zip',) + tuple(clause[1:])],
            ]

    def get_publishing_values(self):
        result = super(Address, self).get_publishing_values()
        result['multiline'] = self.full_address
        result['oneline'] = self.full_address.replace('\n', ' ')
        return result

    def get_icon(self):
        return 'coopengo-address'

    def get_func_key(self, values):
        return '|'.join((self.zip, self.street))

    @classmethod
    def search_func_key(cls, name, clause):
        # TODO : make a better functional key
        assert clause[1] == '='
        operands = clause[2].split('|')
        if len(operands) == 2:
            zip, street = operands
            res = []
            if zip != 'None':
                res.append(('zip', clause[1], zip))
            if street != 'None':
                res.append(('street', clause[1], street))
            return res
        else:
            return ['OR',
                [('zip',) + tuple(clause[1:])],
                [('street',) + tuple(clause[1:])],
                ]

    @classmethod
    def add_func_key(cls, values):
        values['_func_key'] = '|'.join((values['zip'], values['street']))
