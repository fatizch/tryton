# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import export

__all__ = [
    'Party',
    'PartyPaymentTerm',
    'PartyAccount',
    ]


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    @classmethod
    def _export_light(cls):
        return (super(Party, cls)._export_light() |
            set(['supplier_payment_term', 'customer_payment_term']))

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        original_domain = cls.account_payable.domain
        assert original_domain == [
                ('type.payable', '=', True),
                ('party_required', '=', True),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ], original_domain
        cls.account_payable.domain = [['OR', ('type.other', '=', True),
                original_domain[0]], original_domain[1], original_domain[2]]


class PartyPaymentTerm(export.ExportImportMixin, metaclass=PoolMeta):
    __name__ = 'party.party.payment_term'


class PartyAccount(metaclass=PoolMeta):
    __name__ = 'party.party.account'

    @classmethod
    def __setup__(cls):
        super(PartyAccount, cls).__setup__()
        original_domain = cls.account_payable.domain
        assert original_domain == [
               ('type.payable', '=', True),
               ('party_required', '=', True),
               ('company', '=', Eval('context', {}).get('company', -1)),
               ], original_domain
        cls.account_payable.domain = [['OR', ('type.other', '=', True),
                original_domain[0]], original_domain[1], original_domain[2]]
