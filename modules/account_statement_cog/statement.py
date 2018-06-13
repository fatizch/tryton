# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.aggregate import Max, Sum

from trytond.transaction import Transaction
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.model import Unique
from trytond.pyson import Eval, Bool, If
from trytond.wizard import Wizard, StateView, Button, StateAction
from trytond.model import ModelView
from trytond.modules.account_statement.statement import _STATES, _DEPENDS
from trytond.modules.coog_core import fields, export, model


__all__ = [
    'Line',
    'Statement',
    'LineGroup',
    'CancelLineGroup',
    'CancelLineGroupStart',
    ]


class Line:
    'Account Statement Line'
    __metaclass__ = PoolMeta
    __name__ = 'account.statement.line'

    party_payer = fields.Many2One('party.party', 'Payer', required=True,
        states={'readonly': Eval('statement_state') != 'draft'},
        depends=['statement_state'])
    in_bank_deposit_ticket = fields.Function(
        fields.Boolean('In Bank Deposit Ticket'),
        'on_change_with_in_bank_deposit_ticket')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()

        the_table = TableHandler(cls, module_name)
        # Migration from 1.4: Store party_payer
        migrate = False
        if not the_table.column_exist('party_payer'):
            migrate = True
        super(Line, cls).__register__(module_name)
        if migrate:
            cursor.execute("update account_statement_line "
                "set party_payer = party")

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.number.depends += ['in_bank_deposit_ticket']
        cls.number.states['required'] = Bool(Eval('in_bank_deposit_ticket'))
        cls.number.states = {'readonly': Eval('statement_state') != 'draft'}
        cls.number.depends = ['statement_state']
        cls.party.string = 'Beneficiary'
        cls.sequence.states = {'readonly': Eval('statement_state') != 'draft'}
        cls.sequence.depends = ['statement_state']

    @fields.depends('statement')
    def on_change_statement(self):
        self.in_bank_deposit_ticket = \
            self.on_change_with_in_bank_deposit_ticket()

    @fields.depends('statement')
    def on_change_with_in_bank_deposit_ticket(self, name=None):
        return self.statement and self.statement.in_bank_deposit_ticket

    @fields.depends('party_payer', 'amount', 'party', 'invoice')
    def on_change_party_payer(self):
        self.party = self.party_payer
        self.on_change_party()

    def get_synthesis_rec_name(self, name):
        return '%s - %s - %s' % (self.statement.journal.rec_name,
            Pool().get('ir.date').date_as_string(self.date),
            self.statement.journal.currency.amount_as_string(self.amount))

    def create_move(self):
        move = super(Line, self).create_move()
        if move:
            move.description = (self.description
                if self.description else self.statement.journal.rec_name)
            move.save()
        return move

    def get_move_line(self):
        move_line = super(Line, self).get_move_line()
        if not move_line.description and self.number:
            move_line.description = self.number
        return move_line


class Statement(export.ExportImportMixin):
    __name__ = 'account.statement'
    _func_key = 'name'

    in_bank_deposit_ticket = fields.Function(
        fields.Boolean('In Bank Deposit Ticket'),
        'on_change_with_in_bank_deposit_ticket',
        searcher='search_in_bank_deposit_ticket')
    total_statement_amount = fields.Function(
        fields.Numeric('Total Amount'),
        'get_total_statement_amount')
    color = fields.Function(
        fields.Char('Color'),
        'get_color')
    form_color = fields.Function(
        fields.Char('Color'),
        'get_color')

    @classmethod
    def __setup__(cls):
        super(Statement, cls).__setup__()
        cls.lines.depends.append('in_bank_deposit_ticket')
        cls.name.readonly = True
        cls.date.states.update(_STATES)
        cls.date.depends += _DEPENDS
        cls._error_messages.update({
                'empty_lines': 'No lines associated to the statement(s) %s',
                })
        t = cls.__table__()
        cls._sql_constraints += [('statement_uniq_name',
                Unique(t, t.name, t.company),
                'The name on statement must be unique per company')]

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Journal = pool.get('account.statement.journal')
        vlist = [x.copy() for x in vlist]
        for vals in vlist:
            if not vals.get('name'):
                journal_id = vals.get('journal')
                journal = Journal(journal_id)
                vals['name'] = Sequence.get_id(journal.sequence.id)
        return super(Statement, cls).create(vlist)

    @classmethod
    def view_attributes(cls):
        return super(Statement, cls).view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black')
                ), (
                '/form/notebook/page/group/field[@name="state"]',
                'states',
                {'field_color': Eval('form_color')}
                ), (
                '/form/group[@id="invisible"]',
                'states',
                {'invisible': True})
                ]

    @fields.depends('journal')
    def on_change_with_in_bank_deposit_ticket(self, name=None):
        return self.journal and self.journal.process_method == 'cheque'

    @classmethod
    def search_in_bank_deposit_ticket(cls, name, clause):
        return [('journal.process_method', clause[1], 'cheque')]

    @fields.depends('lines')
    def on_change_lines(self):
        # Workaround for issue #2743 : assume that we are in a recursion if
        # last line amount is None
        # Edited for issue #5830: Handle case where an empty line
        # (with an amount of 0) is placed at the end of the list
        if any(x.amount is None for x in self.lines):
            return
        super(Statement, self).on_change_lines()

    def get_total_statement_amount(self, name):
        return sum(l.amount for l in self.lines)

    def get_color(self, name):
        if self.state == 'posted' and name == 'form_color':
            return 'green'
        elif self.state == 'cancel' and name == 'color':
            return 'grey'
        elif self.state == 'cancel' and name == 'form_color':
            return 'red'
        elif self.state == 'validated':
            return 'blue'
        return 'black'

    @classmethod
    def validate_manual(cls):
        pass

    def _group_key(self, line):
        keys = dict(super(Statement, self)._group_key(line))
        # Keep party key as it us used in the odt report
        keys['party'] = line.party_payer
        return tuple([(k, v) for (k, v) in keys.iteritems()])

    def _get_move(self, key):
        move = super(Statement, self)._get_move(key)
        move.description = self.name
        return move

    @classmethod
    def validate_statement(cls, statements):
        errors = []
        for statement in statements:
            if not statement.lines:
                errors.append(statement.name)
        if errors:
            cls.raise_user_error('empty_lines', ', '.join(errors))
        super(Statement, cls).validate_statement(statements)


class LineGroup:
    __metaclass__ = PoolMeta
    __name__ = 'account.statement.line.group'

    cancel_motive = fields.Function(fields.Char('Cancel motive',
            readonly=True),
        'get_cancel_motive')
    is_cancelled = fields.Function(fields.Boolean('Is cancelled',
            states={'invisible': True}, readonly=True),
        'get_is_cancelled')

    @classmethod
    def __setup__(cls):
        super(LineGroup, cls).__setup__()
        cls._buttons.update({
            'start_cancel': {
                'invisible': Eval('is_cancelled')},
            })

    @classmethod
    def view_attributes(cls):
        return super(LineGroup, cls).view_attributes() + [(
                '/tree', 'colors', If(~Eval('is_cancelled'), 'black', 'red')),
            ('/form/group[@id="cancel_button"]', 'states',
                {'invisible': True})]

    @classmethod
    @model.CoogView.button_action(
        'account_statement_cog.act_cancel_line_group')
    def start_cancel(cls, LineGroups):
        pass

    def get_is_cancelled(self, name=None):
        return bool(self.move.cancel_move)

    def get_cancel_motive(self, name=None):
        if self.move and self.move.cancel_move:
            return self.move.cancel_move.description
        return ''

    @classmethod
    def _grouped_columns(cls, line):
        return [
            Max(line.statement).as_('statement'),
            Max(line.number).as_('number'),
            Max(line.date).as_('date'),
            Sum(line.amount).as_('amount'),
            Max(line.party_payer).as_('party'),
            ]


class CancelLineGroupStart(ModelView):
    'Cancel Line Group Start'

    __name__ = 'account.statement.line.group.cancel.start'

    journal = fields.Many2One('account.statement.journal', 'Journal',
        states={'invisible': True}, readonly=True)
    moves = fields.One2Many('account.move', None, 'Moves',
        states={'invisible': True}, readonly=True)
    cancel_motive = fields.Many2One('account.statement.journal.cancel_motive',
        'Cancel Motive', domain=[
            ('journals', '=', Eval('journal')),
            ], depends=['journal'], required=True)


class CancelLineGroup(Wizard):
    'Cancel Line Group'

    __name__ = 'account.statement.line.group.cancel'

    start = StateView('account.statement.line.group.cancel.start',
        'account_statement_cog.line_group_cancel_start_view_form', [
            Button('Cancel', 'end', icon='tryton-cancel'),
            Button('Ok', 'cancel', icon='tryton-ok', default=True),
            ])
    cancel = StateAction('account_statement.act_line_group_form')

    def default_start(self, fields):
        pool = Pool()
        move_ids = Transaction().context.get('active_ids')
        moves = pool.get('account.move').browse(move_ids)
        Journal = pool.get('account.statement.journal')
        journals = []

        for move in moves:
            if move.cancel_move:
                move.raise_user_error('already_cancelled')
            statement_line = pool.get('account.statement.line').search(
                [('move', '=', move.id)], limit=1)[0]
            journals.append(statement_line.statement.journal.id)
        if len(set(journals)) > 1:
            Journal.raise_user_error('cancel_journal_mixin')
        return {
            'journal': journals[0],
            'moves': move_ids,
            'cancel_motive': None,
            }

    def do_cancel(self, action):
        moves = self.start.moves
        for move in moves:
            cancel_motive = self.start.cancel_motive.name
            move.cancel_and_reconcile({'description': cancel_motive})
            move.post([move.cancel_move])
        return action, {}
