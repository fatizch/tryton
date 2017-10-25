# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import export

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    'PartyPaymentTerm',
    'PartyAccount',
    ]


class Party:
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
                ('kind', '=', 'payable'),
                ('company', '=', Eval('context', {}).get('company', -1)),
                ]
        cls.account_payable.domain = [['OR', ('kind', '=', 'other'),
                original_domain[0]], original_domain[1]]


class PartyPaymentTerm(export.ExportImportMixin):
    __metaclass__ = PoolMeta
    __name__ = 'party.party.payment_term'


class PartyAccount:
    __name__ = 'party.party.account'

    @classmethod
    def __setup__(cls):
        super(PartyAccount, cls).__setup__()
        original_domain = cls.account_payable.domain
        assert original_domain == [
               ('kind', '=', 'payable'),
               ('company', '=', Eval('context', {}).get('company', -1)),
               ]
        cls.account_payable.domain = [['OR', ('kind', '=', 'other'),
                original_domain[0]], original_domain[1]]
