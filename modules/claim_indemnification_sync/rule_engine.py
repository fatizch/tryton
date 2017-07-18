# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.server_context import ServerContext

from trytond.modules.coog_core import model

__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_master_indemnification(cls):
        master = ServerContext().get('master_indemnification', None)
        if master is None:
            cls.raise_user_error('missing_master_indemnification')
        return master

    @classmethod
    def _re_master_indemnification_details(cls, args):
        master = cls.get_master_indemnification()
        return [cls.extract_indemnification_details(x)
            for x in master.details]

    @classmethod
    def extract_indemnification_details(cls, detail):
        return model.dictionarize(detail, ['start_date', 'end_date', 'kind',
                'amount_per_unit', 'nb_of_unit', 'unit', 'amount',
                'base_amount'])
