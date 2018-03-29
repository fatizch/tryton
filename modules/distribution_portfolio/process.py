# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction


__all__ = [
    'ContractSubscribe',
    ]


class ContractSubscribe:
    __metaclass__ = PoolMeta
    __name__ = 'contract.subscribe'

    def default_process_parameters(self, name):
        defaults = super(ContractSubscribe, self). \
            default_process_parameters(name)
        if Transaction().context.get('active_model') == 'party.party':
            party_id = Transaction().context.get('active_id', None)
            if party_id:
                party = Pool().get('party.party')(party_id)
                if party.portfolio:
                    candidates = defaults['authorized_distributors']
                    candidates = [x.id for x in party.portfolio.all_children
                        if x.is_distributor
                        and (x.id in candidates or not candidates)]
                    defaults.update({
                        'authorized_distributors': candidates,
                        })
        return defaults
