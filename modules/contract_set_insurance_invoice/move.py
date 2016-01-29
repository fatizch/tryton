from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'PartyBalance',
    ]


class PartyBalance:
    __name__ = 'account.party_balance'

    def invoices_report_for_balance(self, contract):
        if not contract.contract_set:
            return super(PartyBalance, self).invoices_report_for_balance(
                    contract)
        return contract.contract_set.invoices_report()[0]
