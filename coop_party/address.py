#-*- coding:utf-8 -*-
import copy

from trytond.model import fields as fields
from trytond.pool import Pool, PoolMeta
from trytond.modules.coop_utils import DynamicSelection, utils
from trytond.modules.coop_utils import string, business

__all__ = ['Address', 'AddresseKind']


class Address():
    "Address"

    __metaclass__ = PoolMeta

    __name__ = 'party.address'

    start_date = fields.Date('Start Date')
    end_date = fields.Date('End Date')
    kind = fields.Selection('get_possible_address_kind', 'Kind')

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls.city = copy.copy(cls.city)
        if not cls.city.on_change_with:
            cls.city.on_change_with = []
        utils.extend_inexisting(cls.city.on_change_with,
            ['zip', 'country', 'city'])

    @classmethod
    def get_summary(cls, addresses, name=None, at_date=None, lang=None):
        res = {}
        for address in addresses:
            res[address.id] = ''
            indent = 0
            if address.kind:
                res[address.id] = string.get_field_as_summary(address, 'kind',
                    False, at_date, lang=lang)
                indent = 1
            res[address.id] += string.re_indent_text(
                address.get_full_address(name), indent)
        return res

    @staticmethod
    def default_start_date():
        return utils.today()

    @staticmethod
    def get_possible_address_kind():
        return AddresseKind.get_values_as_selection('party.address_kind')

    @staticmethod
    def default_kind():
        'RSE TODO : what if this address kind was removed or modified?'
        return 'main'

    def on_change_with_city(self):
        domain = []
        domain.append(('zip', '=', self.zip))
        domain.append(('country', '=', self.country))
        cities = utils.get_those_objects('country.zipcode', domain)
        if len(cities) > 0:
            return cities[0].city
        return self.city

    @classmethod
    def create(cls, vals):
        address = super(Address, cls).create(vals)
        if not (vals['zip'] and vals['country'] and vals['city']):
            return address
        ZipCode = Pool().get('country.zipcode')
        if len(ZipCode.search(
                [
                    ('zip', '=', vals['zip']),
                    ('country', '=', vals['country']),
                ])) > 0:
            return address
        ZipCode.create(
            {
                'zip': vals['zip'],
                'city': vals['city'],
                'country': vals['country']
            })
        return address

    @staticmethod
    def default_country():
        return business.get_default_country()


class AddresseKind(DynamicSelection):
    'Addresse Kind'

    __name__ = 'party.address_kind'
    _table = 'coop_table_of_table'

    @staticmethod
    def get_class_where_used():
        return [('party.address', 'kind')]
