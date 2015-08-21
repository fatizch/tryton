from trytond.pool import PoolMeta

from trytond.modules.rule_engine import check_args


__metaclass__ = PoolMeta
__all__ = [
    'RuleEngineRuntime',
    ]


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'service' in args:
            return args['service']
        return super(RuleEngineRuntime, cls).get_lowest_level_object(args)

    @classmethod
    @check_args('service')
    def _re_service_expense(cls, args, expense_code):
        del_service = args['service']
        return del_service.get_expense(expense_code, args['currency'])

    @classmethod
    @check_args('service')
    def _re_service_total_expenses(cls, args):
        del_service = args['service']
        return del_service.get_total_expense(args['currency'])
