# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.contract_insurance_process.process import (
    ContractSubscribeFindProcess, ContractSubscribe)


__all__ = [
    'ContractSubscribeFindProcess',
    'ContractGroupSubscribeFindProcess',
    'ContractGroupSubscribe',
    ]


class ContractGroupSubscribeFindProcess(ContractSubscribeFindProcess):
    'Contract Group Subscribe Find Process'

    __name__ = 'contract_group.subscribe.find_process'

    @classmethod
    def __setup__(cls):
        super(ContractGroupSubscribeFindProcess, cls).__setup__()
        cls.product.domain = [
            'AND',
            cls.product.domain,
            [('is_group', '=', True)]]


class ContractGroupSubscribe(ContractSubscribe):
    __name__ = 'contract_group.subscribe'

    @classmethod
    def get_parameters_model(cls):
        return 'contract_group.subscribe.find_process'

    def init_main_object_from_process(self, obj, process_param):
        res, err = super(
            ContractGroupSubscribe, self).init_main_object_from_process(
            obj, process_param)
        if res:
            obj.init_from_product(
                process_param.product, process_param.effective_date)
            obj.subscriber = process_param.party
            obj.is_group = True
        return res, err
