from itertools import groupby
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'Renew',
]


class Renew:
    __name__ = 'contract_term_renewal.renew'

    @classmethod
    def renew_contracts(cls, contracts):
        pool = Pool()
        Contract = pool.get('contract')
        renewed_contracts = super(Renew, cls).renew_contracts(contracts)
        keyfunc = lambda c: c.activation_history[-1].start_date
        renewed_contracts.sort(key=keyfunc)
        for new_start_date, contracts in groupby(renewed_contracts, keyfunc):
            contracts = list(contracts)
            with Transaction().set_context(
                    client_defined_date=new_start_date):
                contracts = Contract.browse([x.id for x in contracts])
                Contract.calculate_prices(contracts, start=new_start_date)
                for contract in contracts:
                    assert contract.start_date == new_start_date
                    contract.invoice_to_end_date()
        return renewed_contracts
