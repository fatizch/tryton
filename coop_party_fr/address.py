import copy

from trytond.model import fields
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool
from trytond.modules.party.address import STATES, DEPENDS
__all__ = ['Address']


class Address():
    'Address'

    __name__ = 'party.address'
    __metaclass__ = PoolMeta

    line2 = fields.Char('Add. complement', 38,
        '''AFNOR - Line 2
        For individual : Delivery Point Access Data
        Door or Letterbox number, floor, staircase
        For companies : Individual Identification Form of Address -
        Given Name, Surname, function, Department''',
        states=STATES, depends=DEPENDS)
    line3 = fields.Char('Building', 38,
        '''AFNOR - Line 3
        Delivery point location
        Wing or Building or Construction or Industrial zone''',
        states=STATES, depends=DEPENDS)

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()
        cls.name = copy.copy(cls.name)
        cls.name.size = 38
        cls.name.string = 'Recipient'
        cls.name.help = '''AFNOR - Line 1
        For individual : Identity of the addressee -
        Form of address or given name or surname...
        For companies : Organization identification -
        Organization name, Legal Status'''

        cls.street = copy.copy(cls.street)
        cls.street.size = 38
        if cls.street.on_change is None:
            cls.street.on_change = []
        cls.street.on_change.append('street')
        cls.street.help = '''AFNOR - Line 4
            Street number or plot and thoroughfare -
            Street or Avenue or Village...'''

        cls.streetbis = copy.copy(cls.streetbis)
        cls.streetbis.size = 38
        cls.streetbis.string = 'Post Office'
        cls.streetbis.help = '''AFNOR - Line 5
            Delivery Service
            Identification Thoroughfare Complement BP (P.O box)
            and Locality (if different from the distribution area indicator'''
        if cls.streetbis.on_change is None:
            cls.streetbis.on_change = []
        cls.streetbis.on_change.append('streetbis')

        cls.city = copy.copy(cls.city)
        if cls.city.on_change is None:
            cls.city.on_change = []
        cls.city.on_change.append('city')
        #Set Siret invisible for person
        cls.siret = copy.copy(cls.siret)
        cls.siret.states = {
            'invisible': Bool(~Eval('_parent_party', {}).get('is_company'))}
        cls.siret_nic.states = {
            'invisible': Bool(~Eval('_parent_party', {}).get('is_company'))}

    def on_change_street(self):
        #AFNOR rule, no comma after street number and line 4 should be upper
        return {'street': self.street.replace(',', '').upper()}

    def on_change_streetbis(self):
        #AFNOR rule, line 5 should be in uppercase
        return {'streetbis': self.streetbis.upper()}

    def on_change_city(self):
        #AFNOR rule, line 6 must be in uppercase
        return {'city': self.city.upper()}

    def get_full_address(self, name):
        res = ''
        if self.name:
            res = self.name + '\n'
        if self.line2:
            res += self.line2 + '\n'
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
