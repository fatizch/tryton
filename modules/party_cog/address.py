# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from collections import OrderedDict

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Bool, Eval
from trytond.server_context import ServerContext

from trytond.modules.coog_core import fields, export, utils, model
from trytond.modules.country_cog import country

__all__ = [
    'Address',
    'Zip',
    ]


class Address(export.ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.address'
    _func_key = 'func_key'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    zip_and_city = fields.Function(
        fields.Many2One('country.zip', 'Zip', states={
            'invisible': ~Eval('zip_and_city') & (
                Bool(Eval('city') & Bool(Eval('zip'))))
            }),
        'get_zip_and_city', 'setter_void', searcher='search_zip_and_city')
    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')
    needs_subdivision = fields.Function(
        fields.Boolean('Needs Subdivision'),
        'on_change_with_needs_subdivision')
    return_to_sender = fields.Function(fields.Boolean('Return To Sender'),
        'get_return_to_sender', setter='set_return_to_sender',
        searcher='search_return_to_sender')
    color = fields.Function(fields.Char('Color', states={'invisile': True}),
        'get_color')
    icon = fields.Function(fields.Char('Icon', states={'invisile': True}),
        'get_icon')
    one_line_street = fields.Function(fields.Char('Street'),
        'on_change_with_one_line_street')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls.city.states['invisible'] = Bool(Eval('zip_and_city') | ~Eval(
                'city'))
        cls.city.depends += ['zip_and_city']
        cls.zip.states['invisible'] = Bool(Eval('zip_and_city') | ~Eval(
                'zip'))
        cls.zip.depends += ['zip_and_city']
        cls.subdivision.states['invisible'] = ~Eval('needs_subdivision')
        cls.subdivision.depends += ['country']
        cls.active.states['invisible'] = True

    @classmethod
    def view_attributes(cls):
        return super(Address, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color')),
            ]

    @classmethod
    def _export_light(cls):
        return set(['country'])

    def get_summary_content(self, label, at_date=None, lang=None):
        return (None, ' '.join(self.full_address.splitlines()))

    @staticmethod
    def get_cities_from_zip(zipcode, country):
        return Pool().get('country.zip').search([
                ('zip', '=', zipcode), ('country', '=', country)])

    @staticmethod
    def get_zips_from_city(city, country):
        return Pool().get('country.zip').search([
                ('city', '=', city), ('country', '=', country)])

    def get_return_to_sender(self, name):
        return not self.active

    @classmethod
    def set_return_to_sender(cls, addresses, name, value):
        cls.write(addresses, {'active': not value})

    @classmethod
    def search_return_to_sender(cls, name, clause):
        reverse = {
            '=': '!=',
            '!=': '=',
            }
        if clause[1] in reverse:
            return [('active', reverse[clause[1]], clause[2])]
        else:
            return []

    def get_color(self, name):
        if self.return_to_sender:
            return 'grey'
        if utils.is_effective_at_date(self):
            return 'blue'
        return 'black'

    def get_icon(self, name=None):
        color = self.get_color(name)
        if color == 'grey':
            return 'cancel-list'
        elif color == 'blue':
            return 'coopengo-address'
        return ''

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

    @fields.depends('address_lines', 'city', 'country', 'zip', 'zip_and_city')
    def on_change_address_lines(self):
        super(Address, self).on_change_address_lines()
        if not self.city or not self.zip:
            return
        data_finder = {'zip': self.zip, 'city': self.city}
        data_finder.update(self.address_lines)
        self.zip_and_city = self.find_zip_and_city(data_finder)
        if self.zip_and_city:
            self.city = self.zip_and_city.city
            self.zip = self.zip_and_city.zip

    @fields.depends('country')
    def on_change_with_needs_subdivision(self, name=None):
        return self.country.code != 'FR' if self.country else True

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

    @classmethod
    def get_domain_for_find_zip_and_city(cls, data):
        return [('city', '=', data.get('city', '')),
            ('zip', '=', data.get('zip', ''))]

    @classmethod
    def find_zip_and_city(cls, data, country=None):
        Zip = Pool().get('country.zip')
        domain = cls.get_domain_for_find_zip_and_city(data)
        if country:
            domain.append(('country', '=', country.id))
        zips = Zip.search(domain)
        if zips:
            return cls._filter_possible_zips(data, zips, country)

    @classmethod
    def _filter_possible_zips(cls, data, zips, country=None):
        if not zips:
            return
        return zips[0]

    def get_zip_and_city(self, name):
        data_finder = {'zip': self.zip, 'city': self.city}
        data_finder.update(self.address_lines or {})
        zip_and_city = self.find_zip_and_city(data_finder, self.country)
        if zip_and_city:
            return zip_and_city.id

    @fields.depends('zip', 'country', 'city', 'zip_and_city', 'address_lines')
    def on_change_zip_and_city(self):
        self.city = self.zip_and_city.city if self.zip_and_city else ''
        self.zip = self.zip_and_city.zip if self.zip_and_city else ''

    def get_address_as_char(self, name, with_return_carriage=False):
        sep = '\n' if with_return_carriage else ' '
        return sep.join(self.get_full_address(None).splitlines())

    def get_rec_name(self, name):
        return self.get_address_as_char(name)

    @staticmethod
    def default_country():
        return getattr(country.Country._default_country(), 'id', None)

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

    def get_func_key(self, values):
        return '|'.join((self.zip or '', self.street or ''))

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
        values['_func_key'] = '|'.join((values['zip'] or '',
                values['street'] or ''))

    @classmethod
    def _get_address_zipcode_equivalent_for_import(cls):
        # careful : the order must be that of args to
        # find_zip_and_city
        res = OrderedDict()
        for fname in ('zip', 'city'):
            res[fname] = fname
        return res

    @classmethod
    def _import_json(cls, values, main_object=None):
        # Update the address with zipcode repository
        equivalents = cls._get_address_zipcode_equivalent_for_import()
        address_fnames = equivalents.keys()
        if all([x in values for x in equivalents.keys()]):
            zip_and_city = cls.find_zip_and_city({
                    f: values.get(f, None)
                    for f in address_fnames
                    })
            for f in address_fnames:
                values[f] = getattr(zip_and_city, equivalents[f], None)
        return super(Address, cls)._import_json(values, main_object)

    @fields.depends('street')
    def on_change_with_one_line_street(self, name=None):
        if not self.street:
            return ''
        return ' '.join(filter(None, (x.strip() for x in
                        self.street.splitlines())))

    def _update_street(self):
        super(Address, self)._update_street()
        self.one_line_street = self.on_change_with_one_line_street()


class Zip:
    __metaclass__ = PoolMeta
    __name__ = 'country.zip'

    @classmethod
    def __setup__(cls):
        super(Zip, cls).__setup__()
        cls._error_messages.update({
                'used_zip_code': 'You cannot modify this zip code:\n'
                ' %(zip_info)s \n'
                ' as it is used in other addresses. Add a new zipcode instead.'
                })

    @classmethod
    def write(cls, *args):
        # Add check to ensure the user does not overwrite a zip code that is
        # used in other addresses
        with model.error_manager():
            if not ServerContext().get('from_batch', None):
                params = iter(args)
                for country_zips, values in zip(params, params):
                    addresses_with_zip = cls.get_country_zips_addresses(
                        country_zips)
                    if addresses_with_zip:
                        cls.append_functional_error(
                            'used_zip_code', {
                                'zip_info': cls.get_zip_info(addresses_with_zip)
                                })
            super(Zip, cls).write(*args)

    @classmethod
    def get_country_zips_addresses(cls, country_zips):
        PartyAddress = Pool().get('party.address')
        country_zips_domains = ['OR']
        for country_zip in country_zips:
            country_zips_domains.append(
                [
                    ('country', '=', country_zip.country),
                    ('zip', '=', country_zip.zip),
                    ('city', '=', country_zip.city),
                    ('subdivision', '=', country_zip.subdivision)
                    ])
        return PartyAddress.search([country_zips_domains])

    @classmethod
    def get_zip_info(cls, addresses_with_zip):
        used_zips = set([a.zip_and_city for a in addresses_with_zip])
        return [' '.join([str(z.zip or ''), str(z.city or ''),
                str(z.subdivision or ''), str(z.country.name or '')])
            for z in used_zips]
