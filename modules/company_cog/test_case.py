# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    main_company_name = fields.Char('Main Company Name')

    @classmethod
    def run_test_case_method(cls, method):
        try:
            company = cls.get_company()
        except:
            company = None
        if company:
            with Transaction().set_context(company=company.id):
                super(TestCaseModel, cls).run_test_case_method(method)
        else:
            super(TestCaseModel, cls).run_test_case_method(method)

    @classmethod
    def create_company(cls, **kwargs):
        Company = Pool().get('company.company')
        return Company(**kwargs)

    @classmethod
    def main_company_test_case(cls):
        Configuration = cls.get_instance()
        User = Pool().get('res.user')
        company_party = cls.create_party(name=Configuration.main_company_name,
            short_name=Configuration.main_company_name)
        company = cls.create_company(party=company_party,
            currency=Configuration.currency)
        company.save()
        for user in User.search([('main_company', '=', None)]):
            user.main_company = company
            user.company = company
            # User already exist in the db, so no auto-save for them
            user.save()

    @classmethod
    def main_company_test_case_test_method(cls):
        try:
            cls.get_company()
            return False
        except:
            return True

    @classmethod
    def get_company(cls):
        Configuration = cls.get_instance()
        if hasattr(Configuration, '_company_cache'):
            return Configuration._company_cache
        Company = Pool().get('company.company')
        companies = Company.search([])
        result = None
        if len(companies) == 1:
            result = companies[0]
        elif len(companies):
            result = Company.search([('party.name', '=',
                    Configuration.main_company_name)])[0]
        if result:
            Configuration._company_cache = result
        if result is None:
            raise Exception('Could not find a valid company')
        return result
