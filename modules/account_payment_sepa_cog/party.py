# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    is_sepa_creditor_identifier_needed = fields.Function(
        fields.Boolean('Need SEPA Creditor Identifier'),
        'get_is_sepa_creditor_identifier_needed')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.sepa_creditor_identifier.states = {
            'invisible': ~Eval('is_sepa_creditor_identifier_needed'),
            }
        cls.sepa_creditor_identifier.depends.append(
            'is_sepa_creditor_identifier_needed')

    @classmethod
    def view_attributes(cls):
        return super(Party, cls).view_attributes() + [(
                '/form/notebook/page[@id="accounting"]/separator[@id="sepa"]',
                'states',
                {'invisible': ~Eval('is_sepa_creditor_identifier_needed')}
                )]

    @classmethod
    def copy(cls, parties, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('sepa_mandates', None)
        return super(Party, cls).copy(parties, default=default)

    @classmethod
    def _export_light(cls):
        return super(Party, cls)._export_light() | {'sepa_mandates'}

    def get_is_sepa_creditor_identifier_needed(self, name):
        company_id = Transaction().context.get('company', None)
        if company_id is None:
            return
        return self == Pool().get('company.company')(company_id).party
