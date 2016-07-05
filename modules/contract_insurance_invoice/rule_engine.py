# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args
from trytond.modules.cog_utils import utils

__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract', 'date')
    def get_billing_information(cls, args):
        contract = args['contract']
        return utils.get_value_at_date(contract.billing_informations,
            args['date'], 'date')

    @classmethod
    @check_args('contract', 'date')
    def _re_get_contract_billing_frequency(cls, args):
        billing_info = cls.get_billing_information(args)
        if billing_info and billing_info.billing_mode:
            return billing_info.billing_mode.frequency

    @classmethod
    @check_args('contract', 'date')
    def _re_get_contract_billing_frequency_string(cls, args):
        billing_info = cls.get_billing_information(args)
        if billing_info and billing_info.billing_mode:
            return billing_info.billing_mode.frequency_string

    @classmethod
    @check_args('contract', 'date')
    def _re_get_contract_direct_debit(cls, args):
        billing_info = cls.get_billing_information(args)
        if billing_info and billing_info.billing_mode:
            return billing_info.direct_debit

    @classmethod
    @check_args('contract', 'date')
    def _re_get_contract_direct_debit_day(cls, args):
        billing_info = cls.get_billing_information(args)
        if billing_info and billing_info.billing_mode:
            return billing_info.direct_debit_day

    @classmethod
    @check_args('contract', 'date')
    def _re_get_contract_billing_is_once_per_contract(cls, args):
        billing_info = cls.get_billing_information(args)
        if billing_info and billing_info.billing_mode:
            return billing_info.is_once_per_contract
