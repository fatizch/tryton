from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Company',
]


class Company():
    'Company'

    __metaclass__ = PoolMeta
    __name__ = 'company.company'

    fiscal_years = fields.One2Many('account.fiscalyear', 'company',
        'Fiscal Years')

    def _post_import_set_default_accounts(self):
        account_configuration = Pool().get('account.configuration')(0)
        AccountType = Pool().get('account.account.type')
        Account = Pool().get('account.account')
        for name in ('receivable', 'payable'):
            if getattr(account_configuration, 'default_account_%s' % name):
                continue
            account_type = AccountType()
            account_type.name = 'Client %s' % name
            account_type.company = self
            account_type.save()
            account = Account()
            account.company = self
            account.type = account_type
            account.name = 'Default %s account' % name
            account.kind = name
            account.save()
            setattr(account_configuration, 'default_account_%s' % name,
                account)
        account_configuration.save()

    @classmethod
    def __post_import(cls, companies):
        for company in companies:
            with Transaction().set_context(company=company.id):
                company._post_import_set_default_accounts()

    @classmethod
    def _export_force_recreate(cls):
        result = super(Company, cls)._export_force_recreate()
        result.remove('fiscal_years')
        return result
