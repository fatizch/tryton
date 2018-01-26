# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'ContractSubscribeFindProcess',
    ]


class ContractSubscribeFindProcess:
    __metaclass__ = PoolMeta
    __name__ = 'contract.subscribe.find_process'

    authorized_distributors = fields.Many2Many('distribution.network', None,
        None, 'Authorized Distributors for party', states={'invisible': True})
    party_portfolio = fields.Many2One('distribution.network',
        'Party Portfolio', states={'invisible': True})

    @classmethod
    def __setup__(cls):
        super(ContractSubscribeFindProcess, cls).__setup__()
        cls.distributor.domain = [cls.distributor.domain,
            If(Bool(Eval('party_portfolio')),
                [('id', 'in', Eval('authorized_distributors'))],
                [])]
        cls.distributor.depends += ['party_portfolio',
            'authorized_distributors']

    @staticmethod
    def default_authorized_distributors():
        pool = Pool()
        if Transaction().context.get('active_model') == 'party.party':
            party_id = Transaction().context.get('active_id', None)
            if party_id:
                party = pool.get('party.party')(party_id)
                if party.portfolio:
                    return [x.id for x in party.portfolio.all_children
                        if x.is_distributor]
            else:
                return []

    @staticmethod
    def default_party_portfolio():
        pool = Pool()
        if Transaction().context.get('active_model') == 'party.party':
            party_id = Transaction().context.get('active_id', None)
            if party_id:
                party = pool.get('party.party')(party_id)
                if party.portfolio:
                    return party.portfolio.id
