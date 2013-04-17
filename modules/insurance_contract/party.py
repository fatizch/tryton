from trytond.pool import PoolMeta, Pool

_all_ = [
    'Party',
]


class Party:
    'Party'

    __name__ = 'party.party'
    __metaclass__ = PoolMeta

    def get_subscribed_contracts(self):
        Contract = Pool().get('ins_contract.contract')
        return Contract.search(['subscriber', '=', self.id])
