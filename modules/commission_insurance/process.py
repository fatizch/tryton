# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import utils


__all__ = [
    'ContractSubscribe',
    ]


class ContractSubscribe:
    __metaclass__ = PoolMeta
    __name__ = 'contract.subscribe'

    def init_main_object_from_process(self, contract, process_param):
        res, errs = super(ContractSubscribe,
            self).init_main_object_from_process(contract, process_param)
        if res and getattr(process_param, 'distributor', None):
            contract.broker_party = process_param.distributor.broker_party
            contract.agent = utils.auto_complete_with_domain(contract, 'agent')
            if contract.agent:
                contract.agency = process_param.distributor
        return res, errs
