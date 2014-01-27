import datetime
from decimal import Decimal

from trytond.cache import Cache
from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import coop_date, fields

MODULE_NAME = 'account_cog'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    fiscal_year_sync_date = fields.Date('Fiscal Year Sync Date')
    fiscal_year_periods_frequency = fields.Selection([
            ('1', 'Monthly'),
            ('3', 'Quarterly'),
            ('6', 'Half yearly'),
            ('12', 'Yearly'),
            ], 'Fiscal Year periods frequency')

    _get_account_kind_cache = Cache('get_account_kind')
    _get_account_cache = Cache('get_account')

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['party_test_case']['dependencies'].add(
            'configure_accounting_test_case')
        result['account_kind_test_case'] = {
            'name': 'Account Kind Test Case',
            'dependencies': set(['main_company_test_case']),
        }
        result['account_test_case'] = {
            'name': 'Account Test Case',
            'dependencies': set(['account_kind_test_case']),
        }
        result['configure_accounting_test_case'] = {
            'name': 'Accounting Configuration Test Case',
            'dependencies': set(['account_test_case']),
        }
        result['tax_test_case'] = {
            'name': 'Tax Test Case',
            'dependencies': set(['account_kind_test_case']),
        }
        result['fiscal_year_test_case'] = {
            'name': 'Fiscal Year Test Case',
            'dependencies': set(['main_company_test_case'])}
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
        accounts = []
        translater = cls.get_translater(MODULE_NAME)
        accounts.append(cls.create_account(translater(
                    'Default Payable Account'),
                'payable', translater('Client Payable')))
        accounts.append(cls.create_account(translater(
                    'Default Receivable Account'),
                'receivable', translater('Client Receivable')))
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
        account_config.save()

    @classmethod
    def create_tax_from_line(cls, tax_data):
        translater = cls.get_translater(MODULE_NAME)
        TaxDescription = Pool().get('account.tax.description')
        TaxDescriptionVersion = Pool().get('account.tax.description.version')
        tax = TaxDescription()
        tax.code = tax_data[0]
        tax.name = tax_data[1]
        tax.description = tax_data[5]
        version = TaxDescriptionVersion()
        version.kind = tax_data[4]
        version.value = Decimal(tax_data[3])
        version.start_date = datetime.datetime.strptime(tax_data[2],
            '%d/%m/%Y').date()
        tax.versions = [version]
        tax.account_for_billing = cls.create_account(translater(
                'Account for %s') % tax.code,
            'other', translater('Tax Account'))
        return tax

    @classmethod
    def tax_test_case(cls):
        cls.load_resources(MODULE_NAME)
        tax_file = cls.read_data_file('taxes', MODULE_NAME, ';')
        taxes = []
        for tax_data in tax_file:
            taxes.append(cls.create_tax_from_line(tax_data))
        return taxes

    @classmethod
    def create_fiscal_year(cls, start_date):
        translater = cls.get_translater(MODULE_NAME)
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        Sequence = pool.get('ir.sequence')
        post_move_sequence = Sequence()
        post_move_sequence.company = cls.get_company()
        post_move_sequence.name = '%s - %s %s' % (translater(
                'Post Move Sequence'), translater('Fiscal Year'),
            start_date.year)
        post_move_sequence.code = 'account.move'
        post_move_sequence.save()
        fiscal_year = FiscalYear()
        fiscal_year.start_date = start_date
        fiscal_year.end_date = coop_date.add_day(coop_date.add_year(
                start_date, 1), -1)
        fiscal_year.name = '%s %s' % (translater('Fiscal Year'),
            start_date.year)
        fiscal_year.code = '%s_%s' % (translater('fiscal_year'),
            start_date.year)
        fiscal_year.company = cls.get_company()
        fiscal_year.post_move_sequence = post_move_sequence
        fiscal_year.save()
        return fiscal_year

    @classmethod
    def fiscal_year_test_case(cls):
        FiscalYear = Pool().get('account.fiscalyear')
        fiscal_years = []
        for x in range(0, 20):
            date = datetime.date(datetime.date.today().year + x,
                cls.get_instance().fiscal_year_sync_date.month,
                cls.get_instance().fiscal_year_sync_date.day)
            if FiscalYear.search([('start_date', '=', date)]):
                continue
            fiscal_years.append(cls.create_fiscal_year(date))
        FiscalYear.create_period(fiscal_years, int(
                cls.get_instance().fiscal_year_periods_frequency))
