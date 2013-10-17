from trytond.pool import Pool, PoolMeta
from trytond.modules.coop_utils import set_test_case

MODULE_NAME = 'life_billing_collective_fr'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    @set_test_case('Create Account Kinds')
    def account_kind_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        result = super(TestCaseModel, cls).account_kind_test_case()
        result.append(cls.create_account_kind(translater('Suspense Account')))
        return result

    @classmethod
    @set_test_case('Create default accounts', 'account_kind_test_case')
    def account_test_case(cls):
        result = super(TestCaseModel, cls).create_default_accounts()
        translater = cls.get_translater(MODULE_NAME)
        result.append(cls.create_account(translater(
                    'Default Suspense Account'),
                'other', translater('Suspense Account')))
        return result

    @classmethod
    @set_test_case('Configure Accounting', 'account_test_case')
    def configure_accounting_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        account_config = Pool().get('account.configuration').search([])[0]
        if not account_config.default_suspense_account:
            account_config.default_suspense_account = cls.get_account(
                translater('Default Suspense Account'))
            account_config.save()
