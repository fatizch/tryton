# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Bool, Eval
from trytond.wizard import Wizard, StateView, Button
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, model, coog_date, utils
from trytond.modules.currency_cog import ModelCurrency

__all__ = [
    'MoveLine',
    'OpenPartyBalance',
    'PartyBalance',
    'PartyBalanceLine',
    ]

_FIELDS = ['all_lines', 'lines', 'hide_reconciled_lines',
    'from_date', 'contract', 'hide_canceled_invoices', 'party',
    'scheduled_lines',
    ]


class MoveLine:
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'

    bank_account = fields.Function(
        fields.Many2One('bank.account', 'Bank Account',
            states={'invisible': ~Eval('bank_account')}),
        'get_bank_account')

    def get_bank_account(self, name):
        if self.origin_item:
            if getattr(self.origin_item, 'bank_account', None):
                return self.origin_item.bank_account.id
            elif getattr(self.origin_item, 'sepa_mandate', None):
                return self.origin_item.sepa_mandate.account_number.account.id


class PartyBalanceLine(model.CoogView):
    'Party Balance Line'

    __name__ = 'account.party_balance.line'

    description = fields.Char('Description')
    contract = fields.Char('Contract')
    amount = fields.Numeric('Amount', digits=(16, 2))
    reconciliations_string = fields.Char('Reconciliations')
    reconciled_with = fields.Many2Many('account.move.line', None, None,
        'Reconciled with')
    date = fields.Date('Date')
    party = fields.Char('Party')
    color = fields.Char('Color')
    icon = fields.Char('Icon')
    move_line = fields.Many2One('account.move.line', 'Move Line')
    bank_account = fields.Char('Bank Account',
        states={'invisible': ~Eval('bank_account')})
    childs = fields.One2Many('account.party_balance.line', None,
        'Childs')
    origin = fields.Reference('Origin', selection='get_origin',
        readonly=True)

    @classmethod
    def __setup__(cls):
        super(PartyBalanceLine, cls).__setup__()
        cls._error_messages.update({
                'overpayment_substraction': 'Overpayment Substraction',
                'scheduled_term_of': 'Scheduled Term Of',
                })

    @classmethod
    def view_attributes(cls):
        return super(PartyBalanceLine, cls).view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black'))]

    def init_from_move_line(self, line, scheduled=False):
        self.move_line = line
        self.date = line.post_date
        self.icon = line.icon
        self.color = line.color if not scheduled else 'blue'
        self.amount = line.amount
        if line.account.kind == 'payable':
            self.amount *= -1
        self.party = line.party.rec_name
        if not scheduled:
            self.description = line.synthesis_rec_name
        self.bank_account = (line.bank_account.rec_name if line.bank_account
            else None)
        if line.reconciliation:
            self.reconciliations_string = line.reconciliation.rec_name
            self.reconciled_with = [x for x in line.reconciliation.lines
                if x != line]
        self.contract = line.contract.rec_name if line.contract else None
        self.origin = line.origin

    def add_childs_to_scheduled_term_line(self, components):
        Line = Pool().get('account.party_balance.line')
        childs = []
        for component in components:
            new_line = Line(amount=component['amount'], date=self.date,
                contract=self.contract)
            if component['kind'] == 'line_to_pay':
                move_line = component['line']
                new_line.init_from_move_line(move_line, scheduled=True)
            new_line.description = new_line.get_scheduled_child_description(
                component)
            childs.append(new_line)
        self.childs = childs

    def get_scheduled_term_parent_description(self, components):
        Date = Pool().get('ir.date')
        return '%s %s' % (
            self.raise_user_error('scheduled_term_of', raise_exception=False),
            Date.date_as_string(self.date)
            )

    def get_scheduled_child_description(self, component):
        term = None
        if component['kind'] == 'line_to_pay':
            description = component['line'].synthesis_rec_name
            term = component['term']
        elif component['kind'] == 'overpayment_substraction':
            description = self.raise_user_error(
                'overpayment_substraction', raise_exception=False)
        else:
            description = component['invoice'].invoice.get_synthesis_rec_name(
                None)
            term = component['term']
        if term and not term.is_one_shot:
            description += ' | %s' % term.rec_name
        return description

    @classmethod
    def get_origin(cls):
        Move = Pool().get('account.move')
        return Move.get_origin()


class PartyBalance(ModelCurrency, model.CoogView):
    'Party Balance'

    __name__ = 'account.party_balance'

    all_lines = fields.Char('Lines', states={'invisible': True})
    lines = fields.One2Many('account.party_balance.line', None,
        'Accounting Lines', readonly=True)
    scheduled_lines = fields.One2Many('account.party_balance.line', None,
        'Scheduled Lines', readonly=True)
    balance_today = fields.Numeric('Balance Today',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    balance = fields.Numeric('Balance ',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    is_balance_positive = fields.Boolean('Balance Positive',
        states={'invisible': True})
    hide_reconciled_lines = fields.Boolean('Hide Reconciled Lines')
    from_date = fields.Date('From Date')
    party = fields.Many2One('party.party', 'Party', readonly=True)
    contracts = fields.Many2Many('contract', None, None, 'Contracts',
        states={'invisible': True})
    contract = fields.Many2One('contract', 'Contract',
        states={'invisible': ~Eval('contracts')},
        domain=[('id', 'in', Eval('contracts'))], depends=['contracts'])
    hide_canceled_invoices = fields.Boolean('Hide Canceled Invoices')
    currency = fields.Many2One('currency.currency', 'Currency')

    @classmethod
    def __setup__(cls):
        super(PartyBalance, cls).__setup__()
        cls._buttons.update({
                'refresh': {},
                })

    @classmethod
    def view_attributes(cls):
        return super(PartyBalance, cls).view_attributes() + [(
                "/form/group/group/image[@name='traffic_light_red']",
                'states',
                {'invisible': ~Eval('is_balance_positive')},
                ), (
                "/form/group/group/image[@name='traffic_light_green']",
                'states',
                {'invisible': Bool(Eval('is_balance_positive'))},
                )]

    def invoices_report_for_balance(self, contract):
        return contract.invoices_report()[0]

    def show_line(self, line):
        return (not line.reconciliation or not self.hide_reconciled_lines
            ) and (not self.from_date or
                (line.post_date or datetime.date.max) >= self.from_date
            ) and (
                not self.contract or self.contract == line.contract
            ) and (
                not line.is_invoice_canceled
                or not self.hide_canceled_invoices
            )

    def add_parent_line(self, sub_lines, lines):
        Line = Pool().get('account.party_balance.line')
        if len(sub_lines) > 1:
            parent_line = Line(**sub_lines[0]._values)
            parent_line.amount = sum(x.amount for x in sub_lines)
            reconciliations = set([x.move_line.reconciliation
                    for x in sub_lines
                    if x.move_line and x.move_line.reconciliation])
            parent_line.reconciliations_string = ', '.join(
                [r.rec_name for r in reconciliations])
            reconciled_with = []
            for line in sub_lines:
                if hasattr(line, 'reconciled_with'):
                    reconciled_with += line.reconciled_with
            parent_line.reconciled_with = list(set(reconciled_with))
            contracts = set([x.contract for x in sub_lines if x.contract])
            parent_line.contract = (list(contracts)[0]
                if len(contracts) == 1 else None)
            parent_line.childs = sub_lines
            for line in sub_lines:
                line.parent = parent_line
            lines.append(parent_line)

    @model.CoogView.button_change(*_FIELDS)
    def refresh(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Line = pool.get('account.party_balance.line')
        lines = []
        scheduled_lines = []
        # Manage the case where there aren't any lines
        all_lines = self.all_lines.split(',') if self.all_lines else []
        for x in all_lines and MoveLine.browse([int(x) for x in all_lines]):
            if not self.show_line(x):
                continue
            fake_line = Line()
            fake_line.init_from_move_line(x)
            lines.append(fake_line)

        # 2nd Pass to add the check line
        moves = set([x.move_line.move for x in lines
                if x.move_line.origin_item
                and x.move_line.origin_item.__name__ == 'account.statement'
                ])
        for move in moves:
            sub_lines = [x for x in lines
                if getattr(x.move_line, 'move', None) == move]
            self.add_parent_line(sub_lines, lines)

        # 3rd Pass for grouped payments
        tuples = set([
                (x.move_line.origin_item.merged_id,
                    x.move_line.post_date or x.move_line.create_date)
                for x in lines
                if getattr(x.move_line, 'origin_item', None)
                and x.move_line.origin_item.__name__ == 'account.payment'
                and x.move_line.origin.id >= 0
                and x.move_line.origin_item.merged_id])
        for (merged_id, date) in tuples:
            sub_lines = [x for x in lines
                if getattr(x.move_line, 'origin_item', None)
                and x.move_line.origin_item.__name__ == 'account.payment'
                and x.move_line.origin_item.merged_id == merged_id
                and (x.move_line.post_date or x.create_date) == date]
            self.add_parent_line(sub_lines, lines)

        # add scheduled payment
        if self.contract:
            terms = self.invoices_report_for_balance(self.contract)
            for term in terms:
                fake_line = Line(contract=self.contract.rec_name,
                    color='blue', icon='future_blue')
                fake_line.amount = term['total_amount']
                fake_line.date = term['planned_payment_date']
                fake_line.description = \
                    fake_line.get_scheduled_term_parent_description(
                        term['components'])
                fake_line.add_childs_to_scheduled_term_line(
                    term['components'])
                scheduled_lines.append(fake_line)

        def keyfunc(x):
            max_date = datetime.date.max
            move_line = getattr(x, 'move_line', None)
            if move_line:
                return (x.move_line.post_date or datetime.date.max,
                    x.move_line.create_date.date(), x.date)
            else:
                return (max_date, max_date, x.date)

        lines = [x for x in lines if not getattr(x, 'parent', None)]
        lines.sort(key=keyfunc, reverse=True)
        scheduled_lines = [x for x in scheduled_lines
            if not getattr(x, 'parent', None)]
        scheduled_lines.sort(key=keyfunc, reverse=True)

        self.lines = lines
        self.scheduled_lines = scheduled_lines
        if self.contract:
            self.balance_today = self.contract.balance_today
            self.balance = self.contract.balance
            self.is_balance_positive = self.balance_today > 0
        else:
            if self.party.receivable or self.party.receivable_today:
                self.balance_today = self.party.receivable_today
                self.balance = self.party.receivable
                self.is_balance_positive = self.balance_today > 0
            else:
                self.balance_today = self.party.negative_payable_today
                self.balance = self.party.negative_payable
                self.is_balance_positive = self.balance_today < 0

    @fields.depends(*_FIELDS)
    def on_change_contract(self):
        if self.party:
            self.refresh()

    def get_currency(self, name=None):
        return self.currency


class OpenPartyBalance(Wizard):
    'Open Party Balance'

    __name__ = 'account.open_party_balance'

    start_state = 'balance'
    balance = StateView('account.party_balance',
        'account_party_balance.party_balance_view_form', [
            Button('End', 'end', 'tryton-cancel')])

    def default_balance(self, name):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Party = pool.get('party.party')
        Contract = pool.get('contract')
        Company = pool.get('company.company')
        company = Company(Transaction().context['company'])
        if Transaction().context.get('active_model') == 'contract':
            contract = Contract(Transaction().context.get('active_id'))
            contract_id = contract.id
            party = contract.subscriber
        elif Transaction().context.get('active_model') == 'party.party':
            party = Party(Transaction().context.get('active_id'))
            contract_id = None
        lines = MoveLine.search([
                ('party', '=', party),
                ('move_state', '!=', 'draft'),
                ('account.kind', 'in', ['payable', 'receivable']),
                ('move_state', '!=', 'draft'),
                ],
                order=[
                    ('post_date', 'DESC'),
                    ('create_date', 'DESC'),
                    ('date', 'DESC'),
                    ])
        return {
            'all_lines': ','.join([str(x.id) for x in lines]),
            'hide_reconciled_lines': False,
            'hide_canceled_invoices': True,
            'from_date': coog_date.add_year(utils.today(), -1),
            'contracts': [x.id for x in Contract.search([
                        ('subscriber', '=', party),
                        ('status', '!=', 'quote'),
                        ])],
            'contract': contract_id,
            'party': party.id,
            'currency': company.currency.id,
            }
