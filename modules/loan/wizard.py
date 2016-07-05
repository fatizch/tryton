# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'CreateExtraPremium',
    ]


class CreateExtraPremium:
    __name__ = 'contract.option.extra_premium.create'

    def default_extra_premium_data(self, name):
        res = super(CreateExtraPremium, self).default_extra_premium_data(name)
        if Transaction().context.get('active_model') == 'contract':
            contract_id = Transaction().context.get('active_id')
            Contract = Pool().get('contract')
            contract = Contract(contract_id)
            res['is_loan'] = contract.is_loan
        return res
