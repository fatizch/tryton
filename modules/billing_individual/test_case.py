from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache

MODULE_NAME = 'billing_individual'

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel():
    'Test Case Model'

    __metaclass__ = PoolMeta
    __name__ = 'coop_utils.test_case_model'

    _get_account_kind_cache = Cache('get_account_kind')
    _get_account_cache = Cache('get_account')

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['tax_test_case']['dependencies'].add('account_kind_test_case')
        result['account_kind_test_case'] = {
            'name': 'Account Kind Test Case',
            'dependencies': set([]),
        }
        result['account_test_case'] = {
            'name': 'Account Test Case',
            'dependencies': set(['account_kind_test_case']),
        }
        result['configure_accounting_test_case'] = {
            'name': 'Accounting Configuration Test Case',
            'dependencies': set(['account_test_case']),
        }
        return result

    @classmethod
    def create_account_kind(cls, name):
        AccountKind = Pool().get('account.account.type')
        account_kind = AccountKind()
        account_kind.name = name
        account_kind.company = cls.get_company()
        return account_kind

    @classmethod
    def account_kind_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        account_kinds = []
        account_kinds.append(cls.create_account_kind(translater(
                    'Tax Account')))
        account_kinds.append(cls.create_account_kind(translater(
                    'Fee Account')))
        account_kinds.append(cls.create_account_kind(translater(
                    'Product Account')))
        account_kinds.append(cls.create_account_kind(translater(
                    'Coverage Account')))
        account_kinds.append(cls.create_account_kind(translater(
                    'Client Receivable')))
        account_kinds.append(cls.create_account_kind(translater(
                    'Client Payable')))
        account_kinds.append(cls.create_account_kind(translater(
                    'Collection Account')))
        return account_kinds

    @classmethod
    def get_account_kind(cls, name):
        result = cls._get_account_kind_cache.get(name)
        if result:
            return result
        result = Pool().get('account.account.type').search([
                ('name', '=', name),
                ('company', '=', cls.get_company())], limit=1)[0]
        cls._get_account_kind_cache.set(name, result)
        return result

    @classmethod
    def create_account(cls, name, kind, type_name):
        Account = Pool().get('account.account')
        account = Account()
        account.name = name
        account.code = name
        account.kind = kind
        account.type = cls.get_account_kind(type_name)
        account.company = cls.get_company()
        return account

    @classmethod
    def account_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        accounts = []
        accounts.append(cls.create_account(translater(
                    'Default Payable Account'),
                'payable', translater('Client Payable')))
        accounts.append(cls.create_account(translater(
                    'Default Receivable Account'),
                'receivable', translater('Client Receivable')))
        accounts.append(cls.create_account(translater(
                    'Cash Account'),
                'revenue', translater('Collection Account')))
        accounts.append(cls.create_account(translater(
                    'Check Account'),
                'revenue', translater('Collection Account')))
        return accounts

    @classmethod
    def get_account(cls, name):
        result = cls._get_account_cache.get(name)
        if result:
            return result
        result = Pool().get('account.account').search([
                ('name', '=', name),
                ('company', '=', cls.get_company())], limit=1)[0]
        cls._get_account_cache.set(name, result)
        return result

    @classmethod
    def configure_accounting_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        account_config = Pool().get('account.configuration').search([])[0]
        if not account_config.default_account_payable:
            account_config.default_account_payable = cls.get_account(
                translater('Default Payable Account'))
        if not account_config.default_account_receivable:
            account_config.default_account_receivable = cls.get_account(
                translater('Default Receivable Account'))
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

    @classmethod
    def create_tax_from_line(cls, tax_data):
        result = super(TestCaseModel, cls).create_tax_from_line(tax_data)
        translater = cls.get_translater(MODULE_NAME)
        result.account_for_billing = cls.create_account(translater(
                'Account for %s') % result.code,
            'other', translater('Tax Account'))
        return result
