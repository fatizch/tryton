# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.party.address import STATES, DEPENDS

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Address',
    ]


class Address:

    __name__ = 'party.address'

    line3 = fields.Char('Building (Line 3)', help='''AFNOR - Line 3
        Delivery point location
        Wing or Building or Construction or Industrial zone''',
        states=STATES, depends=DEPENDS)

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls.name.string = 'Line 2'
        cls.name.help = '''AFNOR - Line 2
        For individual : Delivery Point Access Data
        Door or Letterbox number, floor, staircase
        For companies : Individual Identification Form of Address -
        Given Name, Surname, function, Department'''

        cls.street.help = '''AFNOR - Line 4
            Street number or plot and thoroughfare -
            Street or Avenue or Village...'''

        cls.streetbis.string = 'Post Office (Line 5)'
        cls.streetbis.help = '''AFNOR - Line 5
            Delivery Service
            Identification Thoroughfare Complement BP (P.O box)
            and Locality (if different from the distribution area indicator'''

        # Set Siret invisible for person
        cls.siret.states = {
            'invisible': Bool(Eval('_parent_party', {}).get('is_person'))}
        cls.siret_nic.states = {
            'invisible': Bool(Eval('_parent_party', {}).get('is_person'))}

    @fields.depends('street')
    def on_change_street(self):
        # AFNOR rule, no comma after street number and line 4 should be upper
        self.street = self.street.replace(',', '').upper()

    @fields.depends('streetbis')
    def on_change_streetbis(self):
        # AFNOR rule, line 5 should be in uppercase
        if self.streetbis:
            self.streetbis = self.streetbis.upper()
        super(Address, self).on_change_streetbis()

    @fields.depends('city')
    def on_change_city(self):
        # AFNOR rule, line 6 must be in uppercase
        self.city = self.city.upper()

    def get_full_address(self, name):
        res = ''
        if self.name:
            res = self.name + '\n'
        if self.line3:
            res += self.line3 + '\n'
        if self.street:
            res += self.street + '\n'
        if self.streetbis:
            res += self.streetbis + '\n'
        if self.zip and self.city:
            res += '%s %s' % (self.zip, self.city)
        if self.country and self.country.code != 'FR':
            res += self.country.name
        return res

    def get_department(self):
        if not self.zip:
            return ''
        if self.zip[0:2] in ['97', '98']:
            return self.zip[0:3]
        if self.zip >= '20000' and self.zip <= '20199':
            return '2A'
        if self.zip >= '20200' and self.zip <= '20999':
            return '2B'
        return self.zip[0:2]

    @classmethod
    def get_domain_for_find_zip_and_city(cls, zip, city, streetbis):
        return super(Address, cls).get_domain_for_find_zip_and_city(
            zip, city, streetbis) + [('line5', '=', streetbis)]

    @fields.depends('zip', 'country', 'city', 'zip_and_city', 'streetbis')
    def on_change_zip_and_city(self):
        super(Address, self).on_change_zip_and_city()
        self.streetbis = (self.zip_and_city.line5) if self.zip_and_city \
            else None

    @classmethod
    def _get_address_zipcode_equivalent_for_import(cls):
        res = super(Address, cls)._get_address_zipcode_equivalent_for_import()
        res.update({'streetbis': 'line5'})
        return res
