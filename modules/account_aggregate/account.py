from sql import Literal
Null = None  # TODO remove when python-sql >=0.3
from sql.aggregate import Max, Sum
from sql.conditionals import Coalesce, Case
from sql.functions import Now

from trytond.pool import PoolMeta, Pool
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval, PYSONEncoder
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond.transaction import Transaction

__all__ = ['Journal', 'Move',
    'Snapshot', 'SnapshotStart', 'SnapshotDone',
    'LineAggregated',
    'OpenLineAggregated', 'OpenLine']
__metaclass__ = PoolMeta


class Journal:
    __name__ = 'account.journal'
    aggregate = fields.Boolean('Aggregate')

    @staticmethod
    def default_aggregate():
        return True


class Move:
    __name__ = 'account.move'
    snapshot = fields.Timestamp('Snapshot', readonly=True, select=True)


class Snapshot(Wizard):
    'Snapshot Moves'
    __name__ = 'account.move.snapshot'
    start = StateView('account.move.snapshot.start',
        'account_aggregate.move_snapshot_start_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('OK', 'snap', 'tryton-ok', default=True),
            ])
    snap = StateTransition()
    done = StateView('account.move.snapshot.done',
        'account_aggregate.move_snapshot_done_view_form', [
            Button('OK', 'end', 'tryton-ok', default=True),
            ])

    def transition_snap(self):
        pool = Pool()
        Move = pool.get('account.move')
        move = Move.__table__()
        cursor = Transaction().cursor
        cursor.execute(*move.update(
                [move.snapshot, move.write_date, move.write_uid],
                [Now(), Now(), Transaction().user],
                where=(move.snapshot == Null)
                & (move.post_date != Null)))
        return 'done'


class SnapshotStart(ModelView):
    'Snapshot Moves'
    __name__ = 'account.move.snapshot.start'


class SnapshotDone(ModelView):
    'Snapshot Moves'
    __name__ = 'account.move.snapshot.done'


class LineAggregated(ModelSQL, ModelView):
    'Account Move Line Aggregated'
    __name__ = 'account.move.line.aggregated'
    account = fields.Many2One('account.account', 'Account')
    journal = fields.Many2One('account.journal', 'Journal')
    post_date = fields.Date('Post Date')
    snapshot = fields.Timestamp('Snapshot', readonly=True, select=True)
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')

    def get_currency_digits(self, name):
        return self.account.currency_digits

    @staticmethod
    def table_query():
        pool = Pool()
        Line = pool.get('account.move.line')
        line = Line.__table__()
        Move = pool.get('account.move')
        move = Move.__table__()
        Journal = pool.get('account.journal')
        journal = Journal.__table__()

        return line.join(move, condition=line.move == move.id
            ).join(journal, condition=move.journal == journal.id
            ).select(
                Max(line.id).as_('id'),
                Literal(0).as_('create_uid'),
                Literal(0).as_('create_date'),
                Literal(0).as_('write_uid'),
                Literal(0).as_('write_date'),
                line.account.as_('account'),
                move.journal.as_('journal'),
                move.post_date.as_('post_date'),
                move.snapshot.as_('snapshot'),
                Sum(Coalesce(line.debit, 0)).as_('debit'),
                Sum(Coalesce(line.credit, 0)).as_('credit'),
                group_by=[
                    line.account,
                    Case((journal.aggregate, move.journal), else_=line.id),
                    move.journal,
                    move.post_date,
                    move.snapshot])


class OpenLineAggregated(Wizard):
    'Open Line Aggregated'
    __name__ = 'account.move.open_line_aggregated'
    start_state = 'open_'
    open_ = StateAction('account_aggregate.act_move_line_aggregated_form')

    def do_open_(self, action):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')

        if not Transaction().context.get('fiscalyear'):
            fiscalyears = FiscalYear.search([
                    ('state', '=', 'open'),
                    ])
        else:
            fiscalyears = [FiscalYear(Transaction().context['fiscalyear'])]

        start_date = min((f.start_date for f in fiscalyears))
        end_date = max((f.end_date for f in fiscalyears))

        action['pyson_domain'] = [
            ('post_date', '>=', start_date),
            ('post_date', '<=', end_date),
            ('account', '=', Transaction().context['active_id']),
            ]
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        return action, {}


class OpenLine(Wizard):
    'Open Line'
    __name__ = 'account.move.line.aggregated.open_line'
    start_state = 'open_'
    open_ = StateAction('account.act_move_line_form')

    def do_open_(self, action):
        pool = Pool()
        LineAggregated = pool.get('account.move.line.aggregated')

        lines = LineAggregated.browse(Transaction().context['active_ids'])

        def domain(line):
            if line.journal.aggregate:
                return [
                    ('account', '=', l.account.id),
                    ('move.journal', '=', l.journal.id),
                    ('move.post_date', '=', l.post_date),
                    ('move.snapshot', '=', l.snapshot),
                    ]
            else:
                return [('id', '=', l.id)]

        action['pyson_domain'] = ['OR'] + [domain(l) for l in lines]
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        return action, {}
