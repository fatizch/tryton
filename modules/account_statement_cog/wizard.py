# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from itertools import groupby
import datetime

from sql import Null
from sql.operators import Like
from decimal import Decimal

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.wizard import StateAction
from trytond.pyson import Eval, Not, Equal, Bool, PYSONEncoder
from trytond.server_context import ServerContext

from trytond.modules.coog_core import model, fields, utils

__all__ = [
    'PaymentInformations',
    'StartCreateStatement',
    'CreateStatement',
    ]


class PaymentInformations(model.CoogView):
    'Payment Informations'
    __name__ = 'account_statement.payment_informations'

    journal = fields.Many2One('account.statement.journal', 'Journal',
        readonly=True)
    process_method = fields.Char('Process Method', readonly=True)
    number = fields.Char('Number', states={
            'invisible': Not(Equal(Eval('process_method'), 'cheque')),
            }, depends=['process_method'])
    description = fields.Char('Description')
    error = fields.Text('Error', states={
            'invisible': ~Eval('error'),
            'readonly': True,
            }, depends=['error'])

    @fields.depends('journal')
    def on_change_with_process_method(self, name=None):
        if self.journal:
            return self.journal.process_method


class StartCreateStatement(model.CoogView):
    'Start Create Statement'
    __name__ = 'account_statement.start_create_statement'

    party = fields.Many2One('party.party', 'Party', required=True,
        readonly=True)
    amount = fields.Numeric('Amount', digits=(16,
            Eval('currency_digits', 2)), required=True,
            depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency',
        required=True)
    currency_digits = fields.Integer('Currency Digits', required=True)
    journal = fields.Many2One('account.statement.journal', 'Journal',
        required=True)
    date = fields.Date('Date', required=True)
    available_lines = fields.Many2Many('account.move.line', None, None,
        'Available Lines')
    lines = fields.Many2Many('account.move.line', None, None, 'Lines To Pay',
        domain=[('id', 'in', Eval('available_lines'))],
        depends=['available_lines'])
    auto_validate = fields.Boolean('Automatically Validate Statement',
        states={'readonly': Bool(Eval('auto_post'))}, depends=['auto_post'])
    auto_post = fields.Boolean('Automatically Post Statement')

    @fields.depends('lines')
    def on_change_with_amount(self, name=None):
        return sum([x.amount for x in self.lines], Decimal(0))

    @fields.depends('journal')
    def on_change_with_auto_post(self, name=None):
        if self.journal:
            return self.journal.auto_post


class CreateStatement(Wizard):
    'Create Statement Wizard'
    __name__ = 'account.statement.create'

    start = StateView('account_statement.start_create_statement',
        'account_statement_cog.start_create_statement_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Payment Informations', 'check_inputs',
                'tryton-go-next', default=True),
            ],
        )
    check_inputs = StateTransition()
    payment_informations = StateView('account_statement.payment_informations',
        'account_statement_cog.payment_informations_view_form', [
            Button('Back', 'start', 'tryton-go-previous'),
            Button('Pay', 'process_pay',
                'tryton-ok', default=True),
            ],
        )
    process_pay = StateTransition()
    statement_view = StateAction(
        'account_statement.act_statement_form')

    @classmethod
    def __setup__(cls):
        super(CreateStatement, cls).__setup__()
        cls._error_messages.update({
                'no_record_selected': 'No record selected',
                'too_many_parties': 'Too many parties selected',
                'no_company': 'No company found',
                'no_currency_for_company': 'No currency for company %s',
                'selection_not_receivable': 'All selected records are not '
                'receivable',
                'amount_not_match': 'The statement amount differs from '
                'calculation: %s > %s (calculated)',
                'missing_cheque_number': 'The cheque number is required',
                'insufficient_amount': 'The amount is insufficient',
                })

    @classmethod
    def get_where_clause_from_context(cls, tables, active_model, instances,
            company, date=None):
        MoveLine = Pool().get('account.move.line')
        line = tables['line']
        account = tables['account']
        move = tables['move']
        line_query, _ = MoveLine.query_get(tables['line'])
        to_compare = date or utils.today()
        date_clause = ((line.maturity_date <= to_compare)
            | (line.maturity_date == Null))
        where_clause = (account.active
            & (account.kind == 'receivable')
            & (line.reconciliation == Null)
            & (account.company == company.id)
            & (Like(move.origin, 'account.invoice,%'))
            & line_query
            & date_clause
            )
        ids = [x.id for x in instances]
        if active_model == 'party.party':
            where_clause &= line.party.in_(ids)
        elif active_model == 'account.move.line':
            where_clause &= line.id.in_(ids)
        elif active_model == 'account.invoice':
            where_clause &= (move.origin.in_([str(x) for x in instances]))
        return where_clause

    @classmethod
    def get_lines_from_context(cls, active_model, instances, company,
            date=None):
        pool = Pool()
        Account = pool.get('account.account')
        MoveLine = pool.get('account.move.line')
        Move = pool.get('account.move')
        cursor = Transaction().connection.cursor()

        tables = {
            'line': MoveLine.__table__(),
            'account': Account.__table__(),
            'move': Move.__table__(),
            }
        query_table = tables['line'].join(tables['account'],
            condition=tables['account'].id == tables['line'].account).join(
                tables['move'], condition=tables['line'].move ==
                tables['move'].id)
        cursor.execute(*query_table.select(tables['line'].id,
                where=cls.get_where_clause_from_context(tables, active_model,
                    instances, company, date)))
        lines = MoveLine.browse([id for id, in cursor.fetchall()])
        return [x for x in lines if x.amount]

    def get_default_values_from_context(self, active_model, instances, company):
        possible_journals = Pool().get('account.statement.journal').search(
            [])
        lines = self.get_lines_from_context(active_model, instances,
            company)
        if hasattr(self.start, 'journal'):
            return {
                'journal': self.start.journal.id,
                'currency': company.currency.id,
                'currency_digits': company.currency.digits,
                'party': self.start.party.id,
                'date': self.start.date,
                'lines': [x.id for x in self.start.lines],
                'auto_validate': self.start.auto_validate,
                'available_lines': [x.id for x in self.start.available_lines],
                'amount': self.start.amount,
                }
        values = {
            'journal': possible_journals[0].id if len(possible_journals) == 1
            else None,
            'currency': company.currency.id,
            'currency_digits': company.currency.digits,
            'party': None,
            'lines': [x.id for x in lines],
            'date': utils.today(),
            'auto_validate': True,
            }
        values['amount'] = sum(x.amount for x in lines)

        if active_model == 'party.party':
            if len(instances) > 1:
                self.raise_user_error('too_many_parties')
            values['party'] = instances[0].id
        elif active_model == 'account.move.line':
            if len(list({x.party.id for x in instances})) > 1:
                self.raise_user_error('too_many_parties')
            if any((x.account.kind != 'receivable' for x in instances)):
                self.raise_user_error('selection_not_receivable')
            values['party'] = instances[0].party.id
        elif active_model == 'account.invoice':
            if len(list({x.party.id for x in instances})) > 1:
                self.raise_user_error('too_many_parties')
            if any((x.type != 'out' for x in instances)):
                self.raise_user_error('selection_not_receivable')
            values['party'] = instances[0].party.id
        values['available_lines'] = [x.id
            for x in self.get_lines_from_context(
                active_model, instances, company, date=datetime.date.max)]
        return values

    def default_start(self, fields):
        pool = Pool()
        context_ = Transaction().context
        company = context_.get('company', None)
        active_ids = context_.get('active_ids')
        active_model = context_.get('active_model')
        if len(active_ids) == 0:
            self.raise_user_error('no_record_selected')
        if not company:
            self.raise_user_error('no_company')
        company = pool.get('company.company')(company)
        if not company.currency:
            self.raise_user_error('no_currency_for_company',
                company.rec_name)
        instances = pool.get(active_model).browse(active_ids)
        return self.get_default_values_from_context(active_model, instances,
            company)

    def default_payment_informations(self, fields):
        return {
            'journal': self.start.journal.id,
            'process_method': self.start.journal.process_method,
            'number': '' if not hasattr(self.payment_informations, 'journal')
            else self.payment_informations.number,
            'description': '' if not hasattr(self.payment_informations,
                'description') else self.payment_informations.description,
            'error': self.payment_informations.error
            if hasattr(self.payment_informations, 'error') else None
            }

    def transition_check_inputs(self):
        calculated_amount = sum(x.amount for x in self.start.lines)
        if self.start.amount > calculated_amount:
            self.raise_user_warning('amount_not_match_%s' %
                str([x.id for x in self.start.lines]), 'amount_not_match', (
                    self.start.amount, calculated_amount))
        if self.start.amount < calculated_amount or not self.start.amount:
            self.raise_user_error('insufficient_amount')
        return 'payment_informations'

    @classmethod
    def group_key(cls, x):
        return x.move.origin

    def fields_error(self, errors=None):
        errors = errors or ''
        if self.payment_informations.process_method == 'cheque':
            if not self.payment_informations.number:
                errors += self.raise_user_error(
                    'missing_cheque_number', raise_exception=False)
        return errors

    def process_other(self):
        pass

    def process_cheque(self):
        pass

    def get_statement_values(self):
        return {
            'journal': self.start.journal,
            'date': self.start.date or utils.today(),
            'start_balance': Decimal('0.00'),
            'end_balance': self.start.amount,
            }

    def get_line_values(self, statement, invoice, line):
        return {
            'party_payer': line.party if line else self.start.party,
            'party': line.party if line else self.start.party,
            'number': self.payment_informations.number,
            'amount': line.amount if line else self.start.amount,
            'account': line.account if line else
            self.start.party.account_receivable_used,
            'invoice': invoice if invoice else None,
            'description': self.payment_informations.description,
            'date': self.start.date,
            'statement': statement,
            }

    def create_statement(self):
        pool = Pool()
        Statement = pool.get('account.statement')
        Line = pool.get('account.statement.line')
        statement_lines = []
        statement = Statement(**self.get_statement_values())
        sorted_lines = sorted(self.start.lines,
            key=self.group_key)
        total_amount = Decimal('0')
        for origin, lines in groupby(sorted_lines,
                self.group_key):
            lines = list(lines)
            for line in lines:
                if origin and origin.__name__ == 'account.invoice':
                    invoice = origin
                else:
                    invoice = None
                statement_line = Line(**self.get_line_values(statement,
                        invoice, line))
                total_amount += line.amount
                statement_lines.append(statement_line)
        if total_amount < self.start.amount:
            if statement_lines:
                statement_lines[-1].amount += self.start.amount - \
                    total_amount
            else:
                statement_lines.append(Line(**self.get_line_values(statement,
                            None, None)))
        statement.total_amount = sum([x.amount for x in statement_lines], 0)
        if statement_lines:
            Line.save(statement_lines)
        statement.lines = statement_lines
        statement.on_change_lines()
        if self.start.auto_validate:
            statement.validate_statement([statement])
        if self.start.auto_post:
            statement.post([statement])
        return statement

    def transition_process_pay(self):
        statement = None
        self.payment_informations.error = self.fields_error()
        if self.payment_informations.error:
            return 'payment_informations'
        process_method = getattr(self, 'process_%s' %
            self.start.journal.process_method)
        error_step = process_method()
        if error_step:
            return error_step
        statement = self.create_statement()
        ServerContext().set_context(created_statement_id=statement.id)
        return 'statement_view'

    def do_statement_view(self, action):
        domain = [('id', '=', ServerContext().get('created_statement_id', None)
                )]
        action.update({'pyson_domain': PYSONEncoder().encode(domain)})
        return action, {}
