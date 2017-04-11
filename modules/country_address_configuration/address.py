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

    address_lines = fields.Function(
        fields.Dict('country.address.line', 'Address Lines', states={
                'invisible': ~Eval('has_address_lines')},
            depends=['has_address_lines']),
        'on_change_with_address_lines', 'setter_void')
    has_address_lines = fields.Function(
        fields.Boolean('Has Address Lines', states={'invisible': True}),
        'on_change_with_has_address_lines')

    @classmethod
    def view_attributes(cls):
        return super(Address, cls).view_attributes() + [(
                '/form/group[@id="left"]/group[@id="street"]',
                'states',
                {'invisible': Bool(Eval('has_address_lines'))}
                )]

    @classmethod
    def setter_void(cls, *args, **kwargs):
        pass

    @fields.depends('country', 'street')
    def on_change_with_address_lines(self, name=None):
        self._update_address_lines()
        return self.address_lines

    def _update_address_lines(self):
        if not self.country:
            self.address_lines = {}
            return
        self.street = self.street or ''
        address_lines = self.country.get_address_lines()
        values = {x: '' for x in address_lines}
        for idx, value in enumerate(self.street.split('\n')):
            if idx >= len(address_lines):
                break
            values[address_lines[idx]] = value
        self.address_lines = values
        self._format_address_lines()

    @fields.depends('country')
    def on_change_with_has_address_lines(self, name=None):
        return bool(self.country) and self.country.get_address_lines()

    @fields.depends('address_lines', 'country', 'street')
    def on_change_address_lines(self):
        self.address_lines = self.address_lines or {}
        self._update_street()
        self.address_lines = self.address_lines.copy()

    @fields.depends('address_lines', 'country', 'street')
    def on_change_country(self):
        if not self.country:
            self.address_lines = {}
            return
        address_lines = self.country.get_address_lines()
        if not address_lines:
            self.address_lines = {}
            return
        self._update_address_lines()
        self.address_lines = self.address_lines.copy()

    def _update_street(self):
        self._format_address_lines()
        if not self.country:
            return
        address_lines = self.country.get_address_lines()
        if address_lines is None:
            return
        self.street = '\n'.join((self.address_lines or {}).get(x, '')
            for x in address_lines)

    def _format_address_lines(self):
        if not self.country:
            return
        if self.address_lines is None:
            self.address_lines = {}
        format_method = getattr(self.__class__, '_format_address_' +
            self.country.code, None)
        if format_method:
            self.address_lines = format_method(self.address_lines)

    @classmethod
    def _format_address_FR(cls, lines):
        res = {}
        for k, v in lines.iteritems():
            res[k] = (v or '').upper()
        return res
