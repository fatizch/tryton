# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.coog_core import fields

__all__ = [
    'Address',
    ]


class Address:
    __metaclass__ = PoolMeta
    __name__ = 'party.address'

    @classmethod
    def __setup__(cls):
        super(Address, cls).__setup__()

        # Set Siret invisible for person
        cls.siret.states = {
            'invisible': Bool(Eval('_parent_party', {}).get('is_person'))}
        cls.siret_nic.states = {
            'invisible': Bool(Eval('_parent_party', {}).get('is_person'))}

    @classmethod
    def _format_address_FR(cls, lines):
        lines = super(Address, cls)._format_address_FR(lines)
        if lines is not None and '4_ligne4' in lines:
            lines['4_ligne4'] = (lines['4_ligne4'] or '').replace(',', '')
        return lines

    @fields.depends('city', 'country')
    def on_change_city(self):
        # AFNOR rule, line 6 must be in uppercase
        if self.country and self.country.code == 'FR':
            self.city = self.city.upper() if self.city else ''

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
    def _filter_possible_zips(cls, data, zips, country=None):
        if not country or country.code != 'FR':
            return super(Address, cls)._filter_possible_zips(data, zips,
                country)
        if not zips:
            return
        matching_line5_zips = [
            z for z in zips if z.line5 == data.get('5_ligne5', '')]
        if matching_line5_zips:
            return matching_line5_zips[0]
        no_line5_zips = [z for z in zips if z.line5 == '']
        if no_line5_zips:
            return no_line5_zips[0]
        return zips[0]

    @fields.depends('zip', 'country', 'city', 'zip_and_city', 'address_lines',
        'street')
    def on_change_zip_and_city(self):
        super(Address, self).on_change_zip_and_city()
        if self.country and self.country.code == 'FR':
            values = (self.address_lines.copy() if self.address_lines else {})
            self.address_lines = values
            self._update_street()

    @classmethod
    def _get_address_zipcode_equivalent_for_import(cls):
        res = super(Address, cls)._get_address_zipcode_equivalent_for_import()
        res.update({'streetbis': 'line5'})
        return res
