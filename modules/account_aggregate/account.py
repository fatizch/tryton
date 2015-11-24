from itertools import groupby

from sql import Literal, Cast, Null
from sql.aggregate import Max, Sum
from sql.conditionals import Coalesce, Case
from sql.functions import ToChar, CurrentTimestamp
from sql.operators import Concat

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, PYSONEncoder
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond.transaction import Transaction

from trytond.modules.cog_utils import fields, model, utils

__metaclass__ = PoolMeta
__all__ = [
    'FiscalYear',
    'Journal',
    'Move',
    'Line',
    'Configuration',
    'Snapshot',
    'TakeSnapshot',
    'SnapshotStart',
    'SnapshotDone',
    'LineAggregated',
    'OpenLineAggregated',
    'OpenLine',
    ]


class FiscalYear:
    __name__ = 'account.fiscalyear'

    export_moves = fields.Boolean('Export Moves',
        help='If not ticked, will filter all moves on this fiscal year out of '
        'snapshot creations')

    @classmethod
    def __register__(cls, module_name):
        # Migration from 1.4 : add export_moves field : Set current fiscal year
        # to export its moves
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().cursor
        do_migrate = False
        table_handler = TableHandler(cursor, cls)
        if not table_handler.column_exist('export_moves'):
            do_migrate = True
        super(FiscalYear, cls).__register__(module_name)
        if not do_migrate:
            return
        table = cls.__table__()
        cursor.execute(*table.update(columns=[table.export_moves],
                values=[Literal(True)], where=(
                    table.start_date <= utils.today())
                & (table.end_date >= utils.today())))
        cursor.execute(*table.update(columns=[table.export_moves],
                values=[Literal(False)], where=(table.export_moves == Null)))


class Journal:
    __name__ = 'account.journal'
    aggregate = fields.Boolean('Aggregate')
    aggregate_posting = fields.Boolean('Aggregate Posting',
        states={
            'invisible': ~Eval('aggregate'),
            },
        depends=['aggregate'])

    @staticmethod
    def default_aggregate():
        return True


class Move:
    __name__ = 'account.move'
    snapshot = fields.Many2One('account.move.snapshot', 'Snapshot',
        select=True, readonly=True)

    @classmethod
    def __setup__(cls):
        super(Move, cls).__setup__()
        cls._check_modify_exclude.append('snapshot')

    @classmethod
    def copy(cls, lines, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('snapshot', None)
        return super(Move, cls).copy(lines, default=default)

    @classmethod
    @model.CoopView.button
    def post(cls, moves):
        pool = Pool()
        Snapshot = pool.get('account.move.snapshot')

        super(Move, cls).post(moves)

        keyfunc = lambda m: m.journal
        moves = cls.browse(sorted(moves, key=keyfunc))

        for journal, moves in groupby(moves, keyfunc):
            moves = list(moves)
            if journal.aggregate and journal.aggregate_posting:
                snapshot, = Snapshot.create([{}])
                cls.write(moves, {
                        'snapshot': snapshot.id,
                        })


class Line:
    __name__ = 'account.move.line'
    snapshot = fields.Function(fields.Many2One('account.move.snapshot',
            'Snapshot'), 'get_move_field', searcher='search_move_field')


class Configuration:
    __name__ = 'account.configuration'

    snapshot_sequence = fields.Property(fields.Many2One('ir.sequence',
            'Snapshot Sequence', required=True, domain=[
                ('code', '=', 'account.move'),
                ]))


class TakeSnapshot(Wizard):
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
        Snapshot = Pool().get('account.move.snapshot')
        Snapshot.take_snapshot()
        return 'done'


class SnapshotStart(model.CoopView):
    'Snapshot Moves'
    __name__ = 'account.move.snapshot.start'


class SnapshotDone(model.CoopView):
    'Snapshot Moves'
    __name__ = 'account.move.snapshot.done'


class Snapshot(model.CoopSQL, model.CoopView):
    'Snapshot Move'
    __name__ = 'account.move.snapshot'
    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(Snapshot, cls).__setup__()
        cls._error_messages.update({
            'no_sequence_defined': 'No sequence defined in configuration'
            })

    @classmethod
    def create(cls, vlist):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Configuration = pool.get('account.configuration')

        config = Configuration(1)
        if not config.snapshot_sequence:
            cls.raise_user_error('no_sequence_defined')
        vlist = [v.copy() for v in vlist]
        for values in vlist:
            if not values.get('name'):
                values['name'] = Sequence.get_id(config.snapshot_sequence.id)
        return super(Snapshot, cls).create(vlist)

    @classmethod
    def take_snapshot(cls):
        pool = Pool()
        Move = pool.get('account.move')
        Period = pool.get('account.period')
        allowed_periods = Period.search([
                ('fiscalyear.export_moves', '=', True)])

        snapshot, = cls.create([{}])
        move = Move.__table__()
        cursor = Transaction().cursor
        cursor.execute(*move.update(
                [move.snapshot, move.write_date, move.write_uid],
                [snapshot.id, CurrentTimestamp(), Transaction().user],
                where=(move.snapshot == Null)
                & (move.post_date != Null)
                & move.period.in_([x.id for x in allowed_periods])))
        return snapshot.id


class LineAggregated(model.CoopSQL, model.CoopView):
    'Account Move Line Aggregated'
    __name__ = 'account.move.line.aggregated'

    aggregated_move_id = fields.Char('Aggregated Move Id')
    account = fields.Many2One('account.account', 'Account',
        ondelete='RESTRICT')
    journal = fields.Many2One('account.journal', 'Journal',
        ondelete='RESTRICT')
    date = fields.Date('Date')
    post_date = fields.Date('Post Date')
    snapshot = fields.Many2One('account.move.snapshot', 'Snapshot',
        ondelete='RESTRICT')
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    description = fields.Char('Description')

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
                Case((journal.aggregate and not journal.aggregate_posting,
                    Literal('')),
                    else_=Max(move.description)).as_('description'),
                Case((journal.aggregate,
                    Concat(ToChar(move.post_date, 'YYYYMMDD'),
                    Cast(move.snapshot, 'VARCHAR'))),
                    else_=Max(move.number)).as_('aggregated_move_id'),
                line.account.as_('account'),
                move.journal.as_('journal'),
                move.date.as_('date'),
                move.post_date.as_('post_date'),
                move.snapshot.as_('snapshot'),
                Sum(Coalesce(line.debit, 0)).as_('debit'),
                Sum(Coalesce(line.credit, 0)).as_('credit'),
                group_by=[
                    line.account,
                    Case((journal.aggregate, move.journal), else_=line.id),
                    journal.aggregate,
                    move.journal,
                    move.date,
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
            if line.journal.aggregate and l.snapshot:
                return [
                    ('account', '=', l.account.id),
                    ('move.journal', '=', l.journal.id),
                    ('move.post_date', '=', l.post_date),
                    ('move.date', '=', l.date),
                    ('move.snapshot', '=', l.snapshot.id),
                    ]
            else:
                return [('id', '=', l.id)]

        action['pyson_domain'] = ['OR'] + [domain(l) for l in lines]
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        return action, {}
