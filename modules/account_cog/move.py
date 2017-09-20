# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from sql import Null
from sql.aggregate import Sum, Max
from sql.conditionals import Case

from trytond import backend
from trytond.transaction import Transaction
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.modules.coog_core import export, fields, utils, coog_string

__metaclass__ = PoolMeta

__all__ = [
    'MoveTemplate',
    'Move',
    'Line',
    'CreateMove',
    'Reconcile',
    'Reconciliation',
    'ReconcileShow',
    'ReconcileLines',
    'ReconcileLinesWriteOff',
    ]


class MoveTemplate(export.ExportImportMixin):
    __name__ = 'account.move.template'

    auto_post_moves = fields.Boolean('Auto Post Generated Moves')


class Move(export.ExportImportMixin):
    __name__ = 'account.move'

    icon = fields.Function(
        fields.Char('Icon'),
        'get_icon')
    kind = fields.Function(
        fields.Selection([('', '')], 'Kind'),
        'get_kind')
    origin_item = fields.Function(
        fields.Reference('Origin', selection='get_origin'),
        'get_origin_item')
    cancel_moves = fields.One2Many('account.move', 'origin', 'Cancel Moves')
    cancel_move = fields.Function(
        fields.Many2One('account.move', 'Cancel Move'),
        'get_cancel_move')
    is_origin_canceled = fields.Function(
        fields.Boolean('Origin Canceled'),
        'get_is_origin_canceled')
    synthesis_rec_name = fields.Function(
        fields.Char('Information'),
        'get_synthesis_rec_name')

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls.origin.select = True

    def get_kind(self, name):
        return ''

    def get_icon(self, name):
        if self.origin_item and getattr(self.origin_item, 'icon', None):
            return self.origin_item.icon
        elif self.is_origin_canceled:
            return 'cancel-list'

    def get_origin_item(self, name):
        if self.origin:
            if self.origin.__name__ == 'account.move':
                origin_item = self.origin.origin_item
            else:
                origin_item = self.origin
            if origin_item:
                return '%s,%s' % (origin_item.__name__, origin_item.id)

    @classmethod
    def get_cancel_move(cls, moves, name):
        cursor = Transaction().connection.cursor()
        res = {x.id: None for x in moves}
        move = cls.__table__()
        cursor.execute(*move.select(move.origin, Max(move.id),
                where=move.origin.in_([str(x) for x in moves]),
                group_by=move.origin
                ))
        for origin, cancel_move in cursor.fetchall():
            res[int(origin.split(',')[1])] = cancel_move
        return res

    def get_is_origin_canceled(self, name):
        return (bool(self.cancel_move)
            or self.origin and self.origin.__name__ == 'account.move')

    def get_synthesis_rec_name(self, name):
        if self.origin:
            if (getattr(self.origin, 'get_synthesis_rec_name', None)
                    is not None):
                return self.origin.get_synthesis_rec_name(name)
            return self.origin.get_rec_name(name)
        elif self.description and self.journal:
            return '%s %s' % (coog_string.translate_value(
                    self.journal, 'type'), self.description)
        elif self.description:
            return self.description
        elif self.journal:
            return self.journal.rec_name
        return self.get_rec_name(name)

    def _cancel_default(self):
        defaults = super(Move, self)._cancel_default()
        if 'date' in defaults or self.date >= utils.today():
            return defaults
        date = utils.today()
        period_id = Pool().get('account.period').find(self.company.id,
            date=date)
        defaults.update({
                'date': date,
                'period': period_id,
                })
        return defaults

    def cancel_and_reconcile(self, description):
        pool = Pool()
        Line = pool.get('account.move.line')
        Reconciliation = pool.get('account.move.reconciliation')
        reconciliations = [x.reconciliation for x in self.lines
            if x.reconciliation]
        if reconciliations:
            Reconciliation.delete(reconciliations)
        cancel_move = self.cancel(default=description)
        to_reconcile = defaultdict(list)
        for line in self.lines + cancel_move.lines:
            if line.account.reconcile:
                to_reconcile[(line.account, line.party)].append(line)
        for lines in to_reconcile.itervalues():
            Line.reconcile(lines)


class Line(export.ExportImportMixin):
    'Account Move Line'

    __name__ = 'account.move.line'

    kind = fields.Function(
        fields.Char('Kind'),
        'get_move_field')
    kind_string = fields.Function(
        fields.Char('Kind'),
        'get_kind_string')
    account_kind = fields.Function(
        fields.Char('Account Kind'), 'get_account_kind')
    reconciled_with = fields.Function(
        fields.Many2Many('account.move.line', None, None, 'Reconciled With'),
        'get_reconciled_with')
    currency_symbol = fields.Function(
        fields.Char('Currency Symbol'), 'get_currency_symbol')
    color = fields.Function(
        fields.Char('Color'),
        'get_color')
    icon = fields.Function(
        fields.Char('Icon'),
        'get_icon')
    origin_item = fields.Function(fields.Reference('Origin',
            selection='get_origin'),
        'get_move_field')
    is_reconciled = fields.Function(
        fields.Boolean('Reconciled'),
        'get_is_reconciled', searcher='search_is_reconciled')
    is_origin_canceled = fields.Function(
        fields.Boolean('Origin Canceled'),
        'get_move_field')
    synthesis_rec_name = fields.Function(
        fields.Char('Information', readonly=True),
        'get_synthesis_rec_name')
    post_date = fields.Function(
        fields.Date('Post Date'),
        'get_move_field', searcher='search_move_field')

    @classmethod
    def __setup__(cls):
        super(Line, cls).__setup__()
        cls.account.select = False
        cls.tax_lines.states['readonly'] = Eval('move_state') == 'posted'
        cls.tax_lines.depends += ['move_state']
        cls._error_messages.update({
                'split_move_description': 'Automatic Split Move',
                })

    @classmethod
    def __register__(cls, module_name):
        super(Line, cls).__register__(module_name)
        TableHandler = backend.get('TableHandler')
        table = TableHandler(cls, module_name)

        # These indexes optimizes invoice generation
        # And certainly other coog services
        table.index_action('account', 'remove')
        table.index_action(['account', 'reconciliation'], 'add')

    @classmethod
    def view_attributes(cls):
        return super(Line, cls).view_attributes() + [(
                '/tree',
                'colors',
                Eval('color', 'black'))]

    @classmethod
    def query_get(cls, table):
        with Transaction().set_context(posted=True):
            return super(Line, cls).query_get(table)

    def get_reconciled_with(self, name):
        if self.reconciliation is None:
            return
        return [line.id for line in self.reconciliation.lines if line != self]

    def get_currency_symbol(self, name):
        return self.account.currency.symbol if self.account else ''

    def get_icon(self, name=None):
        if self.move.icon:
            return self.move.icon
        elif self.is_reconciled:
            return 'coopengo-reconciliation'

    def get_color(self, name):
        if self.move_state == 'draft':
            return 'orange'
        if self.is_origin_canceled:
            return 'red'
        elif self.is_reconciled:
            return 'green'
        return 'black'

    def get_account_kind(self, name):
        return self.account.kind if self.account else ''

    def get_is_reconciled(self, name):
        return self.reconciliation is not None

    def get_synthesis_rec_name(self, name):
        return (self.description if self.description
            else self.move.synthesis_rec_name)

    def get_kind_string(self, name):
        return coog_string.translate(self.move, 'kind')

    def line_match_waterfall_condition(self, line, additionnal_reconciliations,
            journal_code):
        if (line != self and line.reconciliation and
                line.reconciliation != self.reconciliation and
                line.reconciliation not in additionnal_reconciliations and
                line.journal.code == journal_code and
                line.reconciliation.create_date >
                self.reconciliation.create_date):
            return True
        return False

    def waterfall_reconciliations(self, additionnal_reconciliations=None,
            journal_code='SPLIT'):
        '''
        This method returns a list of set of all the reconciliations associated
        to the move line except its own reconciliation.
        The look up is done recursively for each reconciled lines of the
        move of each lines of the current line reconciliation.
        The picked lines are SPLIT lines by default (journal_code
        parameter).
        additionnal_reconciliations parameters is filled during the recursive
        processing and is finally returned.
        '''
        additionnal_reconciliations = additionnal_reconciliations or []
        # We need to get all the move lines of each move for each line of
        # self.reconciliation
        # The line must be reconciled and match the journal_code.
        # The line is not picked if the reconciliation is already in
        # additionnal_reconciliations
        # The create date of the reconcilation must be higher than the
        # self.reconciliation.create_date
        reconciled_lines = [l
            for x in self.reconciliation.lines
            for l in x.move.lines if self.line_match_waterfall_condition(
                l, additionnal_reconciliations, journal_code)]
        if not reconciled_lines:
            return []

        # We want to return all the reconciliation created after
        # self.reconciliation. So we are crawling using a deep recursive
        # algorithm based on the reconciliations creation date.
        # All reconcialiations which depends on the initial reconciliation
        # should be retrieved.
        additionnal_reconciliations.extend(
            [x.reconciliation for x in reconciled_lines])
        for line in reconciled_lines:
            line.waterfall_reconciliations(additionnal_reconciliations)
        return list(set(additionnal_reconciliations))

    @classmethod
    def search_is_reconciled(cls, name, clause):
        if (clause[1] == '=' and clause[2]
                or clause[1] == '!=' and not clause[2]):
            res = [('reconciliation', '!=', None)]
        elif (clause[1] == '=' and not clause[2]
                or clause[1] == '!=' and clause[2]):
            res = [('reconciliation', '=', None)]
        return res

    @classmethod
    def split_lines(cls, splits, journal=None):
        # splits is a list of line / split_amount tuples :
        # Line.split_lines([line1, split1), (line2, split2)], journal=...)
        if not splits:
            return []
        pool = Pool()
        Move = pool.get('account.move')
        split_moves = {}
        split_amounts = {}
        for line, amount_to_split in splits:
            split_amounts[line] = amount_to_split
            split_moves[line] = line.split(amount_to_split, journal)
            split_moves[line].description = cls.get_split_move_description(
                line)
        Move.save(split_moves.values())
        Move.post(split_moves.values())
        split_lines = {}
        for source_line, split_move in split_moves.iteritems():
            # Order of move.lines may not always be keep after saving / posting
            split_amount = split_amounts[source_line]
            split, remaining, compensation = None, None, None
            for line in split_move.lines:
                if abs(line.amount) == abs(source_line.amount):
                    compensation = line
                elif not split and abs(line.amount) == split_amount:
                    split = line
                else:
                    remaining = line
            split_lines[source_line] = (split, remaining, compensation)
        return split_lines

    def split(self, amount_to_split, journal=None):
        pool = Pool()
        Move = pool.get('account.move')
        Line = pool.get('account.move.line')
        Journal = pool.get('account.journal')

        if journal is None:
            journal = Journal.search([('type', '=', 'split')])[0]

        split_move = Move(journal=journal, company=self.move.company,
            date=utils.today())
        split, remaining, compensation = [
            Line(party=self.party, account=self.account, credit=0, debit=0),
            Line(party=self.party, account=self.account, credit=0, debit=0),
            Line(party=self.party, account=self.account, credit=0, debit=0),
            ]

        if self.credit and self.credit > 0 or self.debit and self.debit < 0:
            base = self.credit - self.debit
            source, dest = 'credit', 'debit'
        else:
            base = self.debit - self.credit
            source, dest = 'debit', 'credit'

        assert amount_to_split < base
        setattr(split, source, amount_to_split)
        setattr(remaining, source, base - amount_to_split)
        setattr(compensation, dest, base)
        split_move.lines = [split, remaining, compensation]
        return split_move

    @classmethod
    def get_split_move_description(cls, line):
        return cls.raise_user_error('split_move_description',
            raise_exception=False)

    def _order_move_field(name):
        def order_field(tables):
            pool = Pool()
            Move = pool.get('account.move')
            field = Move._fields[name]
            table, _ = tables[None]
            move_tables = tables.get('move')
            if move_tables is None:
                move = Move.__table__()
                move_tables = {
                    None: (move, move.id == table.move),
                    }
                tables['move'] = move_tables
            return field.convert_order(name, move_tables, Move)
        return staticmethod(order_field)
    order_post_date = _order_move_field('post_date')


class CreateMove:
    __name__ = 'account.move.template.create'

    def create_move(self):
        move = super(CreateMove, self).create_move()

        if self.template.template.auto_post_moves:
            move.post([move])
        return move

    def transition_create_(self):
        # By pass trytond version which never opened the new move
        model = Transaction().context.get('active_model')
        with Transaction().set_context(
                active_model=model if model == 'account.move' else None):
            return super(CreateMove, self).transition_create_()

    def end(self):
        if Transaction().context.get('active_model') == 'account.move':
            return 'reload'


class Reconciliation:
    __name__ = 'account.move.reconciliation'

    @classmethod
    def delete(cls, reconciliations):
        all_reconciliations = []
        for line in sum([[l for l in x.lines if l.journal.code == 'SPLIT']
                    for x in reconciliations], []):
            all_reconciliations.extend(line.waterfall_reconciliations(
                reconciliations + all_reconciliations))
        # Prepare list of split moves which lines will be automatically
        # reconciliated together because each lines are de-reconciled
        split_moves = []
        for line in sum([[l for l in x.lines if l.journal.code == 'SPLIT']
                    for x in all_reconciliations], []):
            if line.move not in split_moves:
                if not any((l.reconciliation for l in line.move.lines)):
                    split_moves.append(line.move)
        super(Reconciliation, cls).delete(
            all_reconciliations or reconciliations)
        if split_moves:
            Line = Pool().get('account.move.line')
            today = utils.today()
            # Reconcile each lines of the split move together
            for move in split_moves:
                Line.reconcile(move.lines, journal=None, date=today)


class Reconcile:
    __name__ = 'account.reconcile'

    def get_accounts(self):
        # Fully override method to filter out draft move lines
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()
        Move = pool.get('account.move')
        move = Move.__table__()
        Account = pool.get('account.account')
        account = Account.__table__()
        cursor = Transaction().connection.cursor()
        balance = line.debit - line.credit
        cond = ((line.reconciliation == Null) & account.reconcile &
            (move.state != 'draft'))
        if Transaction().context['active_model'] == 'party.party':
            cond &= (line.party == Transaction().context['active_id'])
        cursor.execute(*line.join(account,
                condition=line.account == account.id
                ).join(move, condition=line.move == move.id
                ).select(
                account.id,
                where=cond,
                group_by=account.id,
                having=(
                    Sum(Case((balance > 0, 1), else_=0)) > 0)
                & (Sum(Case((balance < 0, 1), else_=0)) > 0)
                ))
        return [a for a, in cursor.fetchall()]

    def get_parties(self, account):
        # Fully override method to filter out draft move lines
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()
        Move = pool.get('account.move')
        move = Move.__table__()
        cursor = Transaction().connection.cursor()

        balance = line.debit - line.credit
        cond = ((line.reconciliation == Null) & (move.state != 'draft')
            & (line.account == account.id))
        if Transaction().context['active_model'] == 'party.party':
            cond &= (line.party == Transaction().context['active_id'])

        cursor.execute(*line.join(move, condition=(line.move == move.id)
                ).select(line.party,
                where=cond,
                group_by=line.party,
                having=(
                    Sum(Case((balance > 0, 1), else_=0)) > 0)
                & (Sum(Case((balance < 0, 1), else_=0)) > 0)
                ))
        return [p for p, in cursor.fetchall()]

    def _all_lines(self):
        # Override to filter draft lines
        pool = Pool()
        Line = pool.get('account.move.line')
        return Line.search([
                ('account', '=', self.show.account.id),
                ('party', '=',
                    self.show.party.id if self.show.party else None),
                ('reconciliation', '=', None),
                ('move_state', '!=', 'draft'),
                ])

    def default_show(self, fields):
        defaults = super(Reconcile, self).default_show(fields)
        defaults['post_leftovers'] = True
        return defaults

    def transition_reconcile(self):
        next_state = super(Reconcile, self).transition_reconcile()
        if not self.show.post_leftovers:
            return next_state

        # Find new moves which were created for profit / loss lines and post
        # those
        new_moves = list(set(x.move
                for origin_line in self.show.lines
                for x in origin_line.reconciliation.lines
                if x.move.state == 'draft'
                and x.move.journal == self.show.journal
                and x.move.date == self.show.date
                ))
        if new_moves:
            Pool().get('account.move').post(new_moves)
        return next_state


class ReconcileShow:
    __name__ = 'account.reconcile.show'

    post_leftovers = fields.Boolean('Post Left Over Moves')

    @classmethod
    def __setup__(cls):
        super(ReconcileShow, cls).__setup__()
        cls.lines.domain = ['AND', cls.lines.domain,
            [('move_state', '!=', 'draft')]]


class ReconcileLines:
    __name__ = 'account.move.reconcile_lines'

    def transition_reconcile(self):
        next_state = super(ReconcileLines, self).transition_reconcile()
        if not getattr(self.writeoff, 'post_writeoff', None):
            return next_state

        # Find new moves which were created for profit / loss lines and post
        # those
        lines = Pool().get('account.move.line').browse(
            Transaction().context.get('active_ids'))
        new_moves = list(set(x.move
                for origin_line in lines
                for x in origin_line.reconciliation.lines
                if x.move.state == 'draft'
                and x.move.journal == self.writeoff.journal
                and x.move.date == self.writeoff.date
                ))
        if new_moves:
            Pool().get('account.move').post(new_moves)
        return next_state


class ReconcileLinesWriteOff:
    __name__ = 'account.move.reconcile_lines.writeoff'

    post_writeoff = fields.Boolean('Post Writeoff Move')

    @classmethod
    def default_post_writeoff(cls):
        return True
