# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'CoveredDataRuleSet',
    ]


class CoveredDataRuleSet:

    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_get_cash_value_payment_mode(cls, args):
        return args['option'].cash_value_payment_mode

    @classmethod
    def _re_get_cash_value_update_date(cls, args):
        date = args['date']
        collection = args['cash_value_collection']
        return (collection.last_update if collection.last_update <= date else
            collection.reception_date)

    @classmethod
    def _re_get_cash_value_update_amount(cls, args):
        date = args['date']
        collection = args['cash_value_collection']
        return (collection.updated_amount if collection.last_update <= date
            else collection.amount)
