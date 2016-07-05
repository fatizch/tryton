# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

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
    fiscal_year_periods_frequency_string = \
        fiscal_year_periods_frequency.translated(
            'fiscal_year_periods_frequency')
    fiscal_year_number = fields.Integer('Number of Fiscal Years to create')
    account_template = fields.Many2One('account.account.template',
        'Account Template', domain=[('parent', '=', None)],
        ondelete='RESTRICT')

    _get_account_kind_cache = Cache('get_account_kind')
    _get_account_cache = Cache('get_account')

    @classmethod
    def create_account_kind(cls, name):
        AccountKind = Pool().get('account.account.type')
        account_kind = AccountKind()
        account_kind.name = name
        account_kind.company = cls.get_company()
        return account_kind

    @classmethod
    def account_kind_test_case(cls):
        configuration = cls.get_instance()
        if configuration.account_template is None:
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
        AccountType = Pool().get('account.account.type')
        result = cls._get_account_kind_cache.get(name)
        if result:
            return AccountType(result)
        result = AccountType.search([
                ('name', '=', name),
                ('company', '=', cls.get_company())], limit=1)[0]
        cls._get_account_kind_cache.set(name, result.id)
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
        configuration = cls.get_instance()
        if (configuration.account_template is None or
                not configuration.account_template.code):
            accounts = []
            translater = cls.get_translater(MODULE_NAME)
            accounts.append(cls.create_account(translater(
                        'Default Payable Account'),
                    'payable', translater('Client Payable')))
            accounts.append(cls.create_account(translater(
                        'Default Receivable Account'),
                    'receivable', translater('Client Receivable')))
            return accounts
        company = cls.get_company()
        # Create account types
        template2type = {}
        configuration.account_template.type.create_type(company.id,
            template2type=template2type)
        # Create accounts
        template2account = {}
        configuration.account_template.create_account(company.id,
            template2account=template2account, template2type=template2type)

    @classmethod
    def get_account(cls, name):
        result = cls._get_account_cache.get(name)
        if result:
            return result
        accounts = Pool().get('account.account').search([
                ('name', '=', name),
                ('company', '=', cls.get_company())], limit=1)
        if accounts:
            result = accounts[0]
            cls._get_account_cache.set(name, result)
            return result

    @classmethod
    def journal_test_case(cls):
        return

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
    def tax_test_case(cls):
        cls.load_resources(MODULE_NAME)
        tax_file = cls.read_data_file('taxes', MODULE_NAME, ';')
        taxes = []
        for tax_data in tax_file:
            taxes.append(cls.create_tax_from_line(tax_data))
        return taxes

    @classmethod
    def create_fiscal_year(cls, **kwargs):
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear(**kwargs)

    @classmethod
    def new_fiscal_year(cls, start_date):
        translater = cls.get_translater(MODULE_NAME)
        return cls.create_fiscal_year(
            start_date=start_date,
            end_date=coop_date.add_day(coop_date.add_year(
                    start_date, 1), -1),
            name='%s %s' % (translater('Fiscal Year'),
                start_date.year),
            code='%s_%s' % (translater('fiscal_year'),
                start_date.year),
            company=cls.get_company(),
            post_move_sequence={
                'company': cls.get_company(),
                'name': '%s - %s %s' % (translater(
                        'Post Move Sequence'), translater('Fiscal Year'),
                    start_date.year),
                'code': 'account.move',
                'prefix': str(start_date.year),
                'padding': 9,
                },
            )

    @classmethod
    def fiscal_year_test_case(cls):
        FiscalYear = Pool().get('account.fiscalyear')
        fiscal_years = []
        for x in range(0, cls.get_instance().fiscal_year_number):
            date = datetime.date(
                cls.get_instance().fiscal_year_sync_date.year + x,
                cls.get_instance().fiscal_year_sync_date.month,
                cls.get_instance().fiscal_year_sync_date.day)
            if FiscalYear.search([('start_date', '=', date)]):
                continue
            fiscal_years.append(cls.new_fiscal_year(date))
        years = FiscalYear.create([x._save_values for x in fiscal_years])
        FiscalYear.create_period(years, int(
                cls.get_instance().fiscal_year_periods_frequency))

    @classmethod
    def fiscal_year_test_case_test_method(cls):
        FY = Pool().get('account.fiscalyear')
        return FY.search_count([]) < cls.get_instance().fiscal_year_number
