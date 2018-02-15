# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import utils
from trytond.modules.contract_process.process import (
    ContractSubscribeFindProcess, ContractSubscribe)


__all__ = [
    'ContractSubscribeFindProcess',
    'ContractGroupSubscribeFindProcess',
    'ContractGroupSubscribe',
    'ImportProcessSelect',
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
            obj.init_from_product(process_param.product)
            obj.subscriber = process_param.party
            obj.is_group = True
        return res, err

    def finalize_main_object(self, obj):
        document_reception = Transaction().context.get(
            'current_document_reception', None)
        if not document_reception:
            return
        document = Pool().get('document.reception')(document_reception)
        document.transfer(obj)


class ImportProcessSelect:
    __metaclass__ = PoolMeta
    __name__ = 'import.process.select'

    @classmethod
    def __setup__(cls):
        super(ImportProcessSelect, cls).__setup__()
        cls._error_messages.update({
                'group_process': 'Subscription Group Process (FR)',
                'group_process_description': 'This process allows '
                'managers to launch a group insurance subscription process',
                })

    def available_processes(self):
        return super(ImportProcessSelect, self).available_processes() + [
            {
                'name': self.raise_user_error(
                    'group_process', raise_exception=False),
                'path':
                'contract_group_process/json/process_life_group_subscription.'
                'json',
                'description': self.raise_user_error(
                    'group_process_description', raise_exception=False),
                'is_visible': utils.is_module_installed('claim_process'),
                },
            ]
