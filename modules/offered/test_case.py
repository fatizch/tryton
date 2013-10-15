from trytond.pool import PoolMeta, Pool
from trytond.modules.coop_utils import fields, set_test_case

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    main_company_name = fields.Char('Main Company Name')

    @classmethod
    def __setup__(cls):
        super(TestCaseModel, cls).__setup__()
        cls.contact_mechanism_test_case._dependencies.append(
            'main_company_test_case')

    @classmethod
    def global_search_list(cls):
        res = super(TestCaseModel, cls).global_search_list()
        res.add('offered.product')
        return res

    @classmethod
    @set_test_case('Main Company Test Case')
    def main_company_test_case(cls):
        Configuration = cls.get_instance()
        User = Pool().get('res.user')
        Company = Pool().get('company.company')
        company_party = cls.create_company(Configuration.main_company_name)[0]
        company = Company()
        company.party = company_party
        company.currency = Configuration.currency
        res = [company]
        for user in User.search([('main_company', '=', None)]):
            user.main_company = company
            res.append(user)
        return res
