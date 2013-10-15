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
        if Company.search([]):
            return
        company_party = cls.create_company(Configuration.main_company_name)[0]
        company = Company()
        company.party = company_party
        company.currency = Configuration.currency
        for user in User.search([('main_company', '=', None)]):
            user.main_company = company
            user.company = company
            # User already exist in the db, so no auto-save for them
            user.save()
        return [company]

    @classmethod
    def get_company(cls):
        Configuration = cls.get_instance()
        if hasattr(Configuration, '_company_cache'):
            return Configuration._company_cache
        Company = Pool().get('company.company')
        result = Company.search([('party.name', '=',
                    Configuration.main_company_name)])[0]
        Configuration._company_cache = result
        return result
