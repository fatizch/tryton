from sql import Literal, Null
from sql.aggregate import Sum

from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import export, fields, utils


__metaclass__ = PoolMeta
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
    __name__ = 'account.open_third_party_balance'

    def do_print_(self, action):
        # Do not call super to avoid trying to set fiscalyear
        data = {
            'company': self.start.company.id,
            'posted': self.start.posted,
            'fiscalyear':
                self.start.fiscalyear.id if self.start.fiscalyear else None,
            }
        data['third_party_balance_option'] = \
            self.start.third_party_balance_option
        data['account'] = self.start.account.id if self.start.account else None
        data['at_date'] = self.start.at_date
        return action, data


class ThirdPartyBalance:
    __name__ = 'account.third_party_balance'

    @classmethod
    def get_context(cls, records, data):
        report_context = super(ThirdPartyBalance, cls).get_context(records,
            data)
        if data['third_party_balance_option'] == 'all':
            return report_context
        pool = Pool()
        Party = pool.get('party.party')
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        Account = pool.get('account.account')
        Company = pool.get('company.company')
        cursor = Transaction().cursor

        line = MoveLine.__table__()
        move = Move.__table__()
        account = Account.__table__()

        company = Company(data['company'])
        report_context['company'] = company
        report_context['digits'] = company.currency.digits
        report_context['fiscalyear'] = data['fiscalyear']
        with Transaction().set_context(context=report_context):
            line_query, _ = MoveLine.query_get(line)
        if data['posted']:
            posted_clause = move.state == 'posted'
        else:
            posted_clause = Literal(True)

        if data['account']:
            account_clause = account.id == data['account']
        else:
            account_clause = Literal(True)

        cursor.execute(*line.join(move, condition=line.move == move.id
                ).join(account, condition=line.account == account.id
                ).select(line.party, Sum(line.debit), Sum(line.credit),
                where=(line.party != Null)
                & account.active
                & account.kind.in_(('payable', 'receivable'))
                & (account.company == data['company'])
                & ((line.maturity_date <= data['at_date'])
                    | (line.maturity_date == Null))
                & (line.reconciliation == Null)
                & line_query & posted_clause
                & account_clause,
                group_by=line.party,
                having=(((Sum(line.debit) != 0) | (Sum(line.credit) != 0)))))

        res = cursor.fetchall()
        id2party = {}
        for party in Party.browse([x[0] for x in res]):
            id2party[party.id] = party
        objects = [{
            'name': id2party[x[0]].rec_name,
            'debit': x[1],
            'credit': x[2],
            'solde': x[1] - x[2],
            } for x in res]
        objects.sort(lambda x, y: cmp(x['name'], y['name']))
        report_context['total_debit'] = sum((x['debit'] for x in objects))
        report_context['total_credit'] = sum((x['credit'] for x in objects))
        report_context['total_solde'] = sum((x['solde'] for x in objects))
        report_context['records'] = objects

        return report_context
