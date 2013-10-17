from trytond.pool import PoolMeta, Pool


MODULE_NAME = 'health_fr'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['expense_kind_test_case'] = {
            'name': 'Expense Kind Test Case',
            'dependencies': set([]),
        }
        result['regime_test_case'] = {
            'name': 'Regime Test Case',
            'dependencies': set([]),
        }
        result['fund_test_case'] = {
            'name': 'Fund Test Case',
            'dependencies': set(['regime_test_case']),
        }
        return result

    @classmethod
    def create_expense_kind_from_line(cls, data):
        ExpenseKind = Pool().get('ins_product.expense_kind')
        expense = ExpenseKind()
        for elem in ('kind', 'code', 'name', 'short_name'):
            setattr(expense, elem, data[elem])
        return expense

    @classmethod
    def expense_kind_test_case(cls):
        cls.load_resources(MODULE_NAME)
        expense_kind_file = cls.read_csv_file('expense_kind.csv', MODULE_NAME,
            reader='dict')
        expense_kinds = []
        for expense_kind_data in expense_kind_file:
            expense_kinds.append(cls.create_expense_kind_from_line(
                    expense_kind_data))
        return expense_kinds

    @classmethod
    def create_regime_from_line(cls, data):
        Regime = Pool().get('health.regime')
        regime = Regime()
        for elem in ('code', 'name', 'short_name'):
            setattr(regime, elem, data[elem])
        return regime

    @classmethod
    def regime_test_case(cls):
        cls.load_resources(MODULE_NAME)
        regime_file = cls.read_csv_file('regime.csv', MODULE_NAME,
            reader='dict')
        regimes = []
        for regime_data in regime_file:
            regimes.append(cls.create_regime_from_line(regime_data))
        return regimes

    @classmethod
    def create_fund_from_line(cls, data, addresses):
        Fund = Pool().get('health.insurance_fund')
        Regime = Pool().get('health.regime')
        fund = Fund()
        for elem in ('code', 'name'):
            setattr(fund, elem, data[elem])
        fund.regime = Regime.search([
                ('code', '=', data['regime_code'].zfill(2))])[0]
        if data['ID_ADR'] in addresses:
            zip_code = addresses[data['ID_ADR']]['Code Postal']
            if zip_code[0:2] in ['97', '98']:
                fund.department = zip_code[0:3]
            else:
                fund.department = zip_code[0:2]
        return fund

    @classmethod
    def fund_test_case(cls):
        cls.load_resources(MODULE_NAME)
        fund_file = cls.read_csv_file('caisse_affiliation.csv', MODULE_NAME,
            reader='dict')
        addresses = dict([(x['ID_ADR'], x) for x in cls.read_csv_file(
                'caisse_affiliation_adresse.csv', MODULE_NAME, reader='dict')])
        funds = []
        for fund_data in fund_file:
            funds.append(cls.create_fund_from_line(fund_data, addresses))
        return funds
