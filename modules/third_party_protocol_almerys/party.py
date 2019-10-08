# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Coalesce

from trytond.config import config
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    almerys_releve_presta = fields.Function(
        fields.Char("Almerys RELEVE_PRESTA"),
        'on_change_with_almerys_releve_presta')
    almerys_courrier_gestion = fields.Function(
        fields.Char("Almerys COURRIER_GESTION"),
        'on_change_with_almerys_courrier_gestion')
    almerys_joignabilite_media = fields.Function(
        fields.Char("Almerys JOIGNABILITE > MEDIA"),
        'on_change_with_almerys_joignabilite_media')
    almerys_joignabilite_adresse_media = fields.Function(
        fields.Char("Almerys JOIGNABILITE > ADRESSE_MEDIA"),
        'on_change_with_almerys_joignabilite_adresse_media')

    def on_change_with_almerys_releve_presta(self, name=None):
        return 'EMAIL'

    def on_change_with_almerys_courrier_gestion(self, name=None):
        return 'EMAIL'

    def on_change_with_almerys_joignabilite_media(self, name=None):
        return 'ME'

    @fields.depends('email')
    def on_change_with_almerys_joignabilite_adresse_media(self, name=None):
        return self.email


class Address(metaclass=PoolMeta):
    __name__ = 'party.address'

    is_person = fields.Function(
        fields.Boolean('Is Person', states={'invisible': True}),
        'on_change_with_is_person', searcher='search_is_person')

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls.street.states['required'] = Bool(Eval('is_person'))
        cls.zip.states['required'] = Bool(Eval('is_person'))
        cls.country.states['required'] = Bool(Eval('is_person'))
        cls.street.depends += ['is_person']
        cls.zip.depends += ['is_person']
        cls.country.depends += ['is_person']

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Address = pool.get('party.address')
        Country = pool.get('country.country')

        super().__register__(module_name)

        # Migration from 2.2
        if config.getboolean('env', 'testing'):
            fr = Country.search([('code', '=', 'FR')])
            if not fr:
                fr = Country(code='FR', name='France')
                fr.save()

        cursor = Transaction().connection.cursor()
        country_t = Country.__table__()
        cursor.execute(*country_t.select(
                country_t.id, where=country_t.code == 'FR'))
        france_id, = cursor.fetchone()

        address_t = Address.__table__()
        cursor.execute(*address_t.update(
                columns=[address_t.street, address_t.zip, address_t.country],
                values=[
                    Coalesce(address_t.street, 'ADRESSE INCONNUE'),
                    Coalesce(address_t.zip, '99999'),
                    Coalesce(address_t.country, france_id)],
                where=((address_t.street == Null)
                    | (address_t.zip == Null)
                    | (address_t.country == Null))))

    @fields.depends('party', '_parent_party.is_person')
    def on_change_with_is_person(self, name=None):
        return self.party and self.party.is_person

    @classmethod
    def search_is_person(cls, name, clause):
        return [('party.is_person',) + tuple(clause[1:])]

    @staticmethod
    def default_zip():
        return '99999'

    @classmethod
    def _format_address_FR(cls, lines):
        lines = super(Address, cls)._format_address_FR(lines)
        if (lines is not None and '2_ligne2' in lines
                and lines['2_ligne2'] == '' and '3_ligne3' in lines
                and lines['3_ligne3'] == '' and '4_ligne4' in lines
                and lines['4_ligne4'] == '' and '5_ligne5' in lines
                and lines['5_ligne5'] == ''):
            lines['4_ligne4'] = (lines['4_ligne4'] or 'ADRESSE INCONNUE'
                ).replace(',', '')
        return lines