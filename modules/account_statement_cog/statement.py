from sql.aggregate import Max, Sum

from trytond.transaction import Transaction
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, export

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    'Statement',
    'LineGroup',
    ]


class Line:
    'Account Statement Line'
    __name__ = 'account.statement.line'

    party_payer = fields.Many2One('party.party', 'Payer', required=True)
    in_bank_deposit_ticket = fields.Function(
        fields.Boolean('In Bank Deposit Ticket'),
        'on_change_with_in_bank_deposit_ticket')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor

        the_table = TableHandler(cursor, cls, module_name)
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
        cls.party.string = 'Beneficiary'

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

    @classmethod
    def __setup__(cls):
        super(Statement, cls).__setup__()
        cls.lines.depends.append('in_bank_deposit_ticket')
        cls.name.readonly = True

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

    @fields.depends('journal')
    def on_change_with_in_bank_deposit_ticket(self, name=None):
        return self.journal and self.journal.bank_deposit_ticket_statement

    def on_change_lines(self):
        # Workaround for issue #2743 : assume that we are in a recursion if
        # last line amount is None
        if self.lines and self.lines[-1].amount is None:
            return
        super(Statement, self).on_change_lines()

    def get_total_statement_amount(self, name):
        return sum(l.amount for l in self.lines)

    @classmethod
    def search_in_bank_deposit_ticket(cls, name, clause):
        return [('journal.bank_deposit_ticket_statement',) + tuple(clause[1:])]

    @classmethod
    def validate_manual(cls):
        pass

    def _group_key(self, line):
        keys = dict(super(Statement, self)._group_key(line))
        # Keep party key as it us used in the odt report
        keys['party'] = line.party_payer
        return tuple([(k, v) for (k, v) in keys.iteritems()])


class LineGroup:
    __name__ = 'account.statement.line.group'

    @classmethod
    def _grouped_columns(cls, line):
        return [
            Max(line.statement).as_('statement'),
            Max(line.number).as_('number'),
            Max(line.date).as_('date'),
            Sum(line.amount).as_('amount'),
            Max(line.party_payer).as_('party'),
            ]
