from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
]


class Contract:
    __name__ = 'contract'

    @classmethod
    def do_renew(cls, contracts, new_start_date):
        pool = Pool()
        RenewalEndorsement = pool.get('endorsement.contract.renew')
        Endorsement = pool.get('endorsement')
        endorsements = RenewalEndorsement.renew_contracts(contracts)
        Endorsement.apply(endorsements)
        cls.save(contracts)

    @classmethod
    def _post_renew_methods(cls):
        methods = super(Contract, cls)._post_renew_methods()
        for method in ['calculate_prices_after_renewal',
                'rebill_after_renewal']:
            if method in methods:
                methods -= {method}
        return methods
