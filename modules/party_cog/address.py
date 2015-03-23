# -*- coding:utf-8 -*-
from collections import OrderedDict
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
        'get_zip_and_city', 'set_zip_and_city', searcher='search_zip_and_city')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()

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

    @fields.depends('zip', 'country', 'zip_and_city')
    def on_change_zip(self):
        if self.zip_and_city and self.zip_and_city.zip == self.zip:
            self.city = self.zip_and_city.city
        elif self.country and self.zip:
            cities = self.get_cities_from_zip(self.zip, self.country)
            if cities:
                self.city = cities[0].city
            else:
                self.city = None

    @fields.depends('city', 'country', 'zip_and_city')
    def on_change_city(self):
        if self.zip_and_city and self.zip_and_city.city == self.city:
            self.zip = self.zip_and_city.zip
        elif self.country and self.city:
            zips = self.get_zips_from_city(self.city, self.country)
            if zips:
                self.zip = zips[0].zip
            else:
                self.zip = None

    @fields.depends('zip', 'country')
    def autocomplete_city(self):
        if self.zip and self.country:
            cities = self.get_cities_from_zip(self.zip, self.country)
            return [x.city for x in cities]
        else:
            return ['']

    @fields.depends('city', 'country')
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

    @fields.depends('street', 'streetbis', 'zip', 'city', 'subdivision',
        'country')
    def get_address_as_char(self, name, with_return_carriage=False):
        full_address = OrderedDict()
        for k in ['street', 'streetbis', 'zip', 'city']:
            full_address[k] = getattr(self, k)
        for k in ['subdivision', 'country']:
            value = getattr(self, k)
            if value:
                full_address[k] = value.name
            else:
                full_address[k] = ''

        full_address['zip_and_city'] = ' '.join(x for x in (full_address[k] for
                k in ['zip', 'city'] if full_address[k]))
        full_address['sub_and_country'] = ' '.join(x for x in (full_address[k]
                for k in ['subdivision', 'country'] if full_address[k]))

        full_address.pop('city')
        full_address.pop('zip')
        full_address.pop('subdivision')
        full_address.pop('country')

        sep = '\n' if with_return_carriage else ' '
        return sep.join(x for x in full_address.values() if x)

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
            ('street',) + tuple(clause[1:]),
            ('city',) + tuple(clause[1:]),
            ('zip',) + tuple(clause[1:]),
            ]

    @classmethod
    def search_zip_and_city(cls, name, clause):
        return [
            ('country',) + tuple(clause[1:]),
            ['OR',
                ('city',) + tuple(clause[1:]),
                ('zip',) + tuple(clause[1:]),
                ],
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
