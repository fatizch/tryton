# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__all__ = [
    'CreateExtraPremium',
    'OptionSubscription',
    ]


class OptionSubscription(metaclass=PoolMeta):
    'Option Subscription'
    __name__ = 'contract.wizard.option_subscription'

    def default_select_package(self, values):
        contract = self.get_contract()
        res = super(OptionSubscription, self).default_select_package(values)
        if contract and contract.is_loan is True:
            res['hide_apply_package_button'] = True
        return res


class CreateExtraPremium(metaclass=PoolMeta):
    __name__ = 'contract.option.extra_premium.create'

    def default_extra_premium_data(self, name):
        res = super(CreateExtraPremium, self).default_extra_premium_data(name)
        if Transaction().context.get('active_model') == 'contract':
            contract_id = Transaction().context.get('active_id')
            Contract = Pool().get('contract')
            contract = Contract(contract_id)
            res['is_loan'] = contract.is_loan
        return res
