from trytond.pool import PoolMeta, Pool


MODULE_NAME = 'contract_insurance_health_fr'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def create_expense_kind_from_line(cls, **kwargs):
        ExpenseKind = Pool().get('expense.kind')
        return ExpenseKind(**kwargs)

    @classmethod
    def expense_kind_test_case(cls):
        ExpenseKind = Pool().get('expense.kind')
        cls.load_resources(MODULE_NAME)
        expense_kind_file = cls.read_csv_file('expense_kind.csv', MODULE_NAME,
            reader='dict')
        expense_kinds = []
        for expense_kind_data in expense_kind_file:
            expense_kinds.append(cls.create_expense_kind_from_line(
                    kind=expense_kind_data['kind'],
                    code=expense_kind_data['code'],
                    name=expense_kind_data['name'],
                    short_name=expense_kind_data['short_name']))
        ExpenseKind.create([x._save_values for x in expense_kinds])

    @classmethod
    def create_hc_system(cls, **kwargs):
        HealthCareSystem = Pool().get('health.care_system')
        return HealthCareSystem(**kwargs)

    @classmethod
    def health_care_system_test_case(cls):
        HealthCareSystem = Pool().get('health.care_system')
        cls.load_resources(MODULE_NAME)
        hc_system_file = cls.read_csv_file('hc_system.csv', MODULE_NAME,
            reader='dict')
        hc_systems = []
        for hc_system_data in hc_system_file:
            hc_systems.append(cls.create_hc_system(
                    code=hc_system_data['code'],
                    name=hc_system_data['name'],
                    short_name=hc_system_data['short_name'],
                    ))
        HealthCareSystem.create([x._save_values for x in hc_systems])

    @classmethod
    def create_fund(cls, **kwargs):
        Fund = Pool().get('health.insurance_fund')
        return Fund(**kwargs)

    @classmethod
    def new_fund(cls, data, addresses):
        HealthCareSystem = Pool().get('health.care_system')
        hc_system = HealthCareSystem.search([
                ('code', '=', data['hc_system_code'].zfill(2))])[0]
        department = ''
        if data['ID_ADR'] in addresses:
            zip_code = addresses[data['ID_ADR']]['Code Postal']
            if zip_code[0:2] in ['97', '98']:
                department = zip_code[0:3]
            else:
                department = zip_code[0:2]
        return cls.create_fund(
            code=data['code'], name=data['name'], hc_system=hc_system,
            department=department)

    @classmethod
    def fund_test_case(cls):
        Fund = Pool().get('health.insurance_fund')
        cls.load_resources(MODULE_NAME)
        fund_file = cls.read_csv_file('caisse_affiliation.csv', MODULE_NAME,
            reader='dict')
        addresses = dict([(x['ID_ADR'], x) for x in cls.read_csv_file(
                'caisse_affiliation_adresse.csv', MODULE_NAME, reader='dict')])
        funds = []
        for fund_data in fund_file:
            funds.append(cls.new_fund(fund_data, addresses))
        Fund.create([x._save_values for x in funds])
