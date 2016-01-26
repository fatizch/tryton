from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields


__all__ = [
    'ContractFee',
    'Premium',
    'PremiumTax',
    'EndorsementContract',
    ]


class ContractFee:
    __metaclass__ = PoolMeta
    _history = True
    __name__ = 'contract.fee'


class Premium:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.premium'

    tax_list = fields.One2Many('contract.premium-account.tax', 'premium',
        'Tax List')

    @classmethod
    def _export_skips(cls):
        return super(Premium, cls)._export_skips() | {'tax_list'}


class PremiumTax:
    _history = True
    __metaclass__ = PoolMeta
    __name__ = 'contract.premium-account.tax'


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    @classmethod
    def _get_restore_history_order(cls):
        order = super(EndorsementContract, cls)._get_restore_history_order()
        contract_idx = order.index('contract')
        order.insert(contract_idx + 1, 'contract.fee')
        order.append('contract.premium')
        order.append('contract.premium-account.tax')
        return order

    @classmethod
    def _prepare_restore_history(cls, instances, at_date):
        super(EndorsementContract, cls)._prepare_restore_history(instances,
            at_date)
        instances['contract.premium'] = []
        for contract in instances['contract']:
            instances['contract.premium'] += contract.premiums
            for fee in contract.fees:
                instances['contract.fee'].append(fee)
                instances['contract.premium'] += fee.premiums
            for option in contract.options:
                instances['contract.premium'] += option.premiums
        for premium in instances['contract.premium']:
            instances['contract.premium-account.tax'] += premium.tax_list
