# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core import fields
from trytond.config import config
from trytond.pyson import Eval, Bool

__all__ = [
    'Party',
    'PartyHexaPoste',
    'PartySSN',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    birth_zip = fields.Char('Birth Zip',
        states={'invisible': ~Eval('is_person')},
        depends=['is_person'])
    birth_city = fields.Char('Birth City',
        states={'invisible': ~Eval('is_person')},
        depends=['is_person'])
    # Search for birth zip is based on zip code if hexaposte nor installed
    # else is based on insee code information. So we use search_with_insee_code
    # context to handle this feature
    birth_zip_and_city = fields.Function(
        fields.Many2One('country.zip', 'Birth Zip and Birth City',
            context={'search_with_insee_code': True},
            domain=[('country', '=', Eval('birth_country'))],
            states={'invisible': ~Eval('is_person')},
            depends=['birth_country', 'is_person']),
        'getter_birth_zip_and_city', 'setter_void',
        )
    birth_country = fields.Many2One('country.country',
        'Birth Country', ondelete='RESTRICT',
        states={'required': Bool(Eval('birth_city')) | Bool(Eval('birth_zip')),
            'invisible': ~Eval('is_person')},
        depends=['birth_city', 'birth_zip', 'is_person'])

    @classmethod
    def default_birth_country(cls):
        code = config.get('options', 'default_country', default='FR')
        Country = Pool().get('country.country')
        country = Country.search([('code', '=', code)])
        if country:
            return country[0].id

    @classmethod
    def setter_void(cls, objects, name, values):
        pass

    @classmethod
    def get_birth_zip_from_code(cls, zip_code, city=None):
        Zip = Pool().get('country.zip')
        domain = [('city', '=', city)] if city else []
        domain.append(((cls.get_var_name_for_zip_search(), '=', zip_code)))
        zips = Zip.search(domain)
        return zips[0] if zips else None

    @classmethod
    def get_var_name_for_zip_search(cls):
        return 'zip'

    def getter_birth_zip_and_city(self, name):
        if not self.birth_zip or not self.birth_city:
            return None
        zip_code = self.__class__.get_birth_zip_from_code(
            self.birth_zip, self.birth_city)
        return zip_code.id if zip_code else None

    @fields.depends('birth_city', 'birth_zip', 'birth_zip_and_city')
    def on_change_birth_zip_and_city(self):
        self.birth_city = self.birth_zip_and_city.city \
            if self.birth_zip_and_city else ''
        self.birth_zip = getattr(self.birth_zip_and_city,
            self.__class__.get_var_name_for_zip_search()) \
            if self.birth_zip_and_city else ''


class PartyHexaPoste(metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def get_var_name_for_zip_search(cls):
        return 'insee_code'


class PartySSN(metaclass=PoolMeta):
    __name__ = 'party.party'

    @fields.depends('ssn', 'ssn_no_key', 'ssn_key')
    def on_change_with_birth_zip_and_city(self, name=None):
        if self.ssn and len(self.ssn[5:10]) == 5:
            zip_code = self.__class__.get_birth_zip_from_code(self.ssn[5:10])
            return zip_code.id if zip_code else None

    @fields.depends('ssn', 'ssn_no_key', 'ssn_key')
    def on_change_with_birth_zip(self, name=None):
        if self.ssn and len(self.ssn[5:10]) == 5:
            zip_code = self.__class__.get_birth_zip_from_code(self.ssn[5:10])
            return getattr(zip_code,
                self.__class__.get_var_name_for_zip_search()) \
                if zip_code else None

    @fields.depends('ssn', 'ssn_no_key', 'ssn_key')
    def on_change_with_birth_city(self, name=None):
        if self.ssn and len(self.ssn[5:10]) == 5:
            zip_code = self.__class__.get_birth_zip_from_code(self.ssn[5:10])
            return zip_code.city if zip_code else None

    @fields.depends('ssn', 'ssn_no_key', 'ssn_key')
    def on_change_with_birth_country(self, name=None):
        if self.ssn and len(self.ssn[5:10]) == 5:
            zip_code = self.__class__.get_birth_zip_from_code(self.ssn[5:10])
            return zip_code.country.id if zip_code else None
