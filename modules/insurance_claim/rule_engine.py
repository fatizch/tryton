from trytond.pool import PoolMeta

from trytond.modules.rule_engine import RuleEngineContext
from trytond.modules.rule_engine import check_args

__all__ = [
    'OfferedContext',
    'ClaimContext',
    ]


class OfferedContext():
    'Offered Context'

    __name__ = 'offered.rule_sets'
    __metaclass__ = PoolMeta

    @classmethod
    def get_lowest_level_object(cls, args):
        if 'delivered_service' in args:
            return args['delivered_service']
        return super(OfferedContext, cls).get_lowest_level_object(args)


class ClaimContext(RuleEngineContext):
    '''
        Context functions for Claims.
    '''
    __name__ = 'ins_product.rule_sets.claim'

    @classmethod
    @check_args('delivered_service')
    def _re_delivered_service_complementary_data(cls, args, data_name):
        cls.append_error(args, 'deprecated_method')

    @classmethod
    @check_args('delivered_service')
    def _re_delivered_service_expense(cls, args, expense_code):
        del_service = args['delivered_service']
        return del_service.get_expense(expense_code, args['currency'])

    @classmethod
    @check_args('delivered_service')
    def _re_delivered_service_total_expenses(cls, args):
        del_service = args['delivered_service']
        return del_service.get_total_expense(args['currency'])
