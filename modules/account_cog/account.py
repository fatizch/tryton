# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null

from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import export, fields, utils


__all__ = [
    'Account',
    'AccountTemplate',
    'AccountKind',
    'AccountTypeTemplate',
    'Journal',
    'FiscalYear',
    'Period',
    'Configuration',
    'ThirdPartyBalance',
    'OpenThirdPartyBalance',
    'OpenThirdPartyBalanceStart',
    'MoveTemplate',
    'MoveTemplateKeyword',
    'MoveLineTemplate',
    'TaxLineTemplate',
    ]


class AccountKind(export.ExportImportMixin):
    __name__ = 'account.account.type'
    _func_key = 'name'

    @classmethod
    def _export_light(cls):
        return super(AccountKind, cls)._export_light() | {'company'}


class AccountTypeTemplate(export.ExportImportMixin):
    __name__ = 'account.account.type.template'

    @classmethod
    def _export_light(cls):
        return super(AccountTypeTemplate, cls)._export_light() | {'parent'}

    @classmethod
    def search_rec_name(cls, name, clause):
        operator, operand = clause[1:]
        if '\\' in operand:
            last = operand.split('\\')[-1]
            previous = '\\'.join(operand.split('\\')[0:-1])
        else:
            previous = None

        if previous:
            return [('name',) + tuple([operator, last]), ('parent.rec_name',
                    operator, previous)]
        else:
            return [('name',) + tuple(clause[1:])]


class Account(export.ExportImportMixin):
    __name__ = 'account.account'
    _func_key = 'code'

    @classmethod
    def is_master_object(cls):
        return True

    @classmethod
    def _export_skips(cls):
        res = super(Account, cls)._export_skips()
        res.add('left')
        res.add('right')
        res.add('taxes')
        res.add('deferrals')
        res.add('childs')
        return res

    @classmethod
    def _export_light(cls):
        return (super(Account, cls)._export_light() |
            set(['company', 'template', 'parent', 'type']))


class AccountTemplate(export.ExportImportMixin):
    __name__ = 'account.account.template'
    _func_key = 'func_key'

    func_key = fields.Function(fields.Char('Functional Key'),
        'get_func_key', searcher='search_func_key')

    @classmethod
    def _export_light(cls):
        return super(AccountTemplate, cls)._export_light() | {'parent'}

    def get_func_key(self, name):
        if self.parent:
            return self.parent.get_func_key(name) + '\\' + self.name
        else:
            return self.name

    @classmethod
    def search_func_key(cls, name, clause):
        operator, operand = clause[1:]
        if '\\' in operand:
            last = operand.split('\\')[-1]
            previous = '\\'.join(operand.split('\\')[0:-1])
        else:
            previous = None

        if previous:
            return [('name',) + tuple([operator, last]), ('parent.func_key',
                    operator, previous)]
        else:
            return [('name',) + tuple(clause[1:])]


class Journal(export.ExportImportMixin):
    __name__ = 'account.journal'
    _func_key = 'code'
    _get_default_journal_cache = Cache('get_default_journal')

    @classmethod
    def _export_skips(cls):
        return super(Journal, cls)._export_skips() | {'view'}

    @classmethod
    def _export_light(cls):
        return super(Journal, cls)._export_light() | {'sequence',
            'credit_account', 'debit_account'}

    @classmethod
    def get_default_journal(cls, type_):
        result = cls._get_default_journal_cache.get(type_, default=0)
        if result is None:
            return None
        elif result:
            return cls(result)
        result = Pool().get('account.journal').search([
                ('type', '=', type_)])
        cls._get_default_journal_cache.set(type_,
            result[0].id if len(result) == 1 else None)
        return result[0] if len(result) == 1 else None


class FiscalYear(export.ExportImportMixin):
    'Fiscal Year'

    __name__ = 'account.fiscalyear'
    _func_key = 'code'

    @classmethod
    def _export_skips(cls):
        return super(FiscalYear, cls)._export_skips() | {'close_lines'}

    @classmethod
    def _export_light(cls):
        return super(FiscalYear, cls)._export_light() | {'company'}


class Period(export.ExportImportMixin):
    __name__ = 'account.period'
    _func_key = 'code'


class Configuration(export.ExportImportMixin):
    __name__ = 'account.configuration'
    _func_key = 'id'

    def export_json(self, skip_fields=None, already_exported=None,
            output=None, main_object=None, configuration=None):
        values = super(Configuration, self).export_json(skip_fields,
            already_exported, output, main_object, configuration)

        for fname in ['default_account_receivable', 'default_account_payable']:
            if fname not in values:
                continue
            field_value = getattr(self, fname)
            values[fname] = {'_func_key': getattr(
                field_value, field_value._func_key)}
        return values

    @classmethod
    def _import_json(cls, values, main_object=None):
        pool = Pool()
        Account = pool.get('account.account')
        for fname in ['default_account_receivable', 'default_account_payable']:
            if fname not in values:
                continue
            account, = Account.search_for_export_import(values[fname])
            values[fname] = account.id

        return super(Configuration, cls)._import_json(values, main_object)


class OpenThirdPartyBalanceStart:
    __metaclass__ = PoolMeta
    __name__ = 'account.open_third_party_balance.start'
    third_party_balance_option = fields.Selection([
            ('all', 'All'),
            ('only_unbalanced', 'Only Unbalanced Party')], 'Balance Option',
        required=True)
    third_party_balance_option_string = third_party_balance_option.translated(
        'third_party_balance_option')
    account = fields.Many2One('account.account', 'Account',
        domain=[('company', '=', Eval('company'))],
        depends=['company'])
    at_date = fields.Date('At date', required=True)

    @classmethod
    def __setup__(cls):
        super(OpenThirdPartyBalanceStart, cls).__setup__()
        cls.fiscalyear.required = False
        # We force to use posted moves only
        cls.posted.states.update({'invisible': True})

    @staticmethod
    def default_posted():
        return True

    @staticmethod
    def default_at_date():
        return utils.today()

    @staticmethod
    def default_third_party_balance_option():
        return 'only_unbalanced'

    @staticmethod
    def default_fiscalyear():
        return None


class OpenThirdPartyBalance:
    __metaclass__ = PoolMeta
    __name__ = 'account.open_third_party_balance'

    def do_print_(self, action):
        # Do not call super to avoid trying to set fiscalyear
        data = {
            'company': self.start.company.id,
            'posted': True,
            'fiscalyear':
                self.start.fiscalyear.id if self.start.fiscalyear else None,
            }
        data['third_party_balance_option'] = \
            self.start.third_party_balance_option
        data['account'] = self.start.account.id if self.start.account else None
        data['at_date'] = self.start.at_date
        return action, data


class ThirdPartyBalance:
    __metaclass__ = PoolMeta
    __name__ = 'account.third_party_balance'

    @classmethod
    def get_query_where(cls, tables, report_context):
        # Force date to defined date to properly filter maturity dates
        at_date = report_context.get('at_date', utils.today())
        with Transaction().set_context(client_defined_date=at_date):
            where = super(ThirdPartyBalance, cls).get_query_where(tables,
                report_context)
        where &= (tables['account.move'].date <= at_date)
        if report_context['account']:
            where &= (
                tables['account.account'].id == report_context['account'])
        if report_context['third_party_balance_option'] == 'only_unbalanced':
            where &= (tables['account.move.line'].reconciliation == Null)
        return where


class MoveTemplate(export.ExportImportMixin):
    __name__ = 'account.move.template'
    _func_key = 'name'

    @classmethod
    def _export_light(cls):
        return super(MoveTemplate, cls)._export_light() | {
            'company', 'journal'}


class MoveTemplateKeyword(export.ExportImportMixin):
    __name__ = 'account.move.template.keyword'

    @classmethod
    def __setup__(cls):
        super(MoveTemplateKeyword, cls).__setup__()
        cls.move.ondelete = 'CASCADE'


class MoveLineTemplate(export.ExportImportMixin):
    __name__ = 'account.move.line.template'

    @classmethod
    def __setup__(cls):
        super(MoveLineTemplate, cls).__setup__()
        cls.move.ondelete = 'CASCADE'

    @classmethod
    def _export_light(cls):
        return super(MoveLineTemplate, cls)._export_light() | {'account'}


class TaxLineTemplate(export.ExportImportMixin):
    __name__ = 'account.tax.line.template'

    @classmethod
    def __setup__(cls):
        super(TaxLineTemplate, cls).__setup__()
        cls.line.ondelete = 'CASCADE'

    @classmethod
    def _export_light(cls):
        return super(TaxLineTemplate, cls)._export_light() | {'code', 'tax'}
