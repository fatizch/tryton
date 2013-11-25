from trytond.pool import Pool, PoolMeta

MODULE_NAME = 'collection'

__all__ = [
    'TestCaseModel',
    ]


# TODO : Make it inherit from the soon to exist coop_account module which will
# include test cases for receivable / payable accounts
class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    @classmethod
    def account_kind_test_case(cls):
        result = []
        translater = cls.get_translater(MODULE_NAME)
        result.append(cls.create_account_kind(translater('Suspense Account')))
        return result

    @classmethod
    def account_test_case(cls):
        result = []
        translater = cls.get_translater(MODULE_NAME)
        result.append(cls.create_account(translater(
                    'Default Suspense Account'),
                'other', translater('Suspense Account')))
        return result

    @classmethod
    def configure_accounting_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        account_config = Pool().get('account.configuration').search([])[0]
        if not account_config.default_suspense_account:
            account_config.default_suspense_account = cls.get_account(
                translater('Default Suspense Account'))
            account_config.save()
