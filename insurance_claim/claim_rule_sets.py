from trytond.modules.rule_engine import RuleEngineContext
from trytond.modules.rule_engine import check_args


class ClaimContext(RuleEngineContext):
    '''
        Context functions for Claims.
    '''
    __name__ = 'ins_product.rule_sets.claim'

    @classmethod
    @check_args('delivered_service')
    def _re_delivered_service_complementary_data(cls, args, data_name):
        del_service = args['delivered_service']
        at_date = args['date']
        return del_service.get_complementary_data_value(at_date, data_name)

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
