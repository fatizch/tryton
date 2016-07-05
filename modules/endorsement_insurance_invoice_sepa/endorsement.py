# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.transaction import Transaction


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    @classmethod
    def update_sepa_mandates(cls, contracts, caller=None):
        if Transaction().context.get('will_be_rollbacked', False):
            return
        if not isinstance(caller, (tuple, list)):
            caller = [caller]
        if caller[0].__name__ != 'endorsement.contract':
            return
        date = caller[0].endorsement.effective_date

        cls.update_mandates_from_date(contracts, date)
