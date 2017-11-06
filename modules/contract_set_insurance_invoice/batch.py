# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import Pool, PoolMeta

__all__ = [
    'RenewContracts',
    ]


class RenewContracts:
    __metaclass__ = PoolMeta
    __name__ = 'contract.renew'

    @classmethod
    def select_ids(cls, *args, **kwargs):
        Contract = Pool().get('contract')
        ids = super(RenewContracts, cls).select_ids(*args, **kwargs)
        contract_set_group = defaultdict(list)
        contracts = Contract.browse(
            [_id for sub_ids in ids for _id in sub_ids])
        for contract in contracts:
            contract_set_group[contract.contract_set].append(contract.id)
        res = []
        # add contract without contract set
        if None in contract_set_group:
            contracts_without_set = contract_set_group.pop(None)
            res += [[(i, ) for i in contracts_without_set]]
        # add all contracts of a set in one task
        for i in contract_set_group.values():
            res.append([(x, ) for x in i])
        return res
