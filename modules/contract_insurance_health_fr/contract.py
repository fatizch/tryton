# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'CoveredElement',
    'Contract',
    ]


class CoveredElement:
    __name__ = 'contract.covered_element'

    is_rsi = fields.Function(
        fields.Boolean('Is RSI', states={'invisible': True}),
        'on_change_with_is_rsi')
    is_law_madelin = fields.Boolean('Law Madelin',
        states={'invisible': ~Eval('is_rsi')})

    @fields.depends('party')
    def on_change_with_is_rsi(self, name=None):
        if self.party and self.party.health_complement:
            hc_system = self.party.health_complement[0].hc_system
            return hc_system.code == '03' if hc_system else False
        return False


class Contract:
    __name__ = 'contract'

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls._error_messages.update({
                'ssn_required': ('SSN is required for covered element %s'),
                })

    @classmethod
    def validate(cls, contracts):
        super(Contract, cls).validate(contracts)
        cls.check_ssn_on_covered_elements(contracts)

    @classmethod
    def check_ssn_on_covered_elements(cls, contracts):
        for contract in contracts:
            for covered in contract.covered_elements:
                if covered.party.get_SSN_required() and not \
                        covered.party.ssn:
                    cls.raise_user_error('ssn_required', covered.rec_name)
