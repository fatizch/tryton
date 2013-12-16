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
    __name__ = 'ir.test_case'

    @classmethod
    def account_kind_test_case(cls):
        result = super(TestCaseModel, cls).account_kind_test_case()
        translater = cls.get_translater(MODULE_NAME)
        result.append(cls.create_account_kind(translater('Suspense Account')))
        result.append(cls.create_account_kind(translater(
                    'Collection Account')))
        return result

    @classmethod
    def account_test_case(cls):
        result = super(TestCaseModel, cls).account_test_case()
        translater = cls.get_translater(MODULE_NAME)
        result.append(cls.create_account(translater(
                    'Default Suspense Account'),
                'other', translater('Suspense Account')))
        result.append(cls.create_account(translater(
                    'Cash Account'),
                'revenue', translater('Collection Account')))
        result.append(cls.create_account(translater(
                    'Check Account'),
                'revenue', translater('Collection Account')))
        return result

    @classmethod
    def configure_accounting_test_case(cls):
        super(TestCaseModel, cls).configure_accounting_test_case()
        translater = cls.get_translater(MODULE_NAME)
        account_config = Pool().get('account.configuration').search([])[0]
        if not account_config.default_suspense_account:
            account_config.default_suspense_account = cls.get_account(
                translater('Default Suspense Account'))
        if not account_config.check_account:
            account_config.check_account = cls.get_account(
                translater('Check Account'))
        if not account_config.cash_account:
            account_config.cash_account = cls.get_account(
                translater('Cash Account'))
        if not account_config.collection_journal:
            account_config.collection_journal = Pool().get(
                'account.journal').search([('type', '=', 'cash')])[0]
        account_config.save()
