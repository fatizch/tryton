from dateutil.relativedelta import relativedelta
from trytond.pool import PoolMeta, Pool

__metaclass__ = PoolMeta
__all__ = [
    'Contract',
]


class Contract:
    __name__ = 'contract'

    @classmethod
    def renew(cls, contracts):
        pool = Pool()
        RenewalEndorsement = pool.get('endorsement.contract.renew')
        Endorsement = pool.get('endorsement')
        to_renew = []
        for contract in contracts:
            if not contract.is_renewable:
                continue
            new_start_date = contract.end_date + relativedelta(days=1)
            if contract.activation_history[-1].start_date == new_start_date:
                continue
            to_renew.append(contract)
        if to_renew:
            endorsements = RenewalEndorsement.renew_contracts(to_renew)
            Endorsement.apply(endorsements)
        return to_renew
