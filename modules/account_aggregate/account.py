# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
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

from trytond.modules.coog_core import fields, model, utils

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
        cursor = Transaction().connection.cursor()
        do_migrate = False
        table_handler = TableHandler(cls)
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
    @model.CoogView.button
    def post(cls, moves):
        pool = Pool()
        Snapshot = pool.get('account.move.snapshot')

        super(Move, cls).post(moves)

        move_groups = cls.group_moves_for_snapshots(moves)
        if not move_groups:
            return

        snapshots = Snapshot.create([{} for _ in xrange(len(move_groups))])
        to_write = sum([[move_group, {'snapshot': snapshot.id}]
            for move_group, snapshot in zip(move_groups, snapshots)], [])

        cls.write(*to_write)

    @classmethod
    def group_moves_for_snapshots(cls, moves):
        def keyfunc(m):
            return m.journal

        moves = cls.browse(sorted(moves, key=keyfunc))

        groups = []
        for journal, moves in groupby(moves, keyfunc):
            if journal.aggregate and journal.aggregate_posting:
                moves = list(moves)
                groups.append(moves)
        return groups


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


class SnapshotStart(model.CoogView):
    'Snapshot Moves'
    __name__ = 'account.move.snapshot.start'


class SnapshotDone(model.CoogView):
    'Snapshot Moves'
    __name__ = 'account.move.snapshot.done'


class Snapshot(model.CoogSQL, model.CoogView):
    'Snapshot Move'
    __name__ = 'account.move.snapshot'
    name = fields.Char('Name', required=True)

    @classmethod
    def __setup__(cls):
        super(Snapshot, cls).__setup__()
        cls._error_messages.update({
            'no_sequence_defined': 'No sequence defined in configuration',
            'no_fiscal_year': 'No fiscal year defined with the Export Moves'
            ' option',
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
        if not allowed_periods:
            cls.raise_user_error('no_fiscal_year')

        snapshot, = cls.create([{}])
        move = Move.__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*move.update(
                [move.snapshot, move.write_date, move.write_uid],
                [snapshot.id, CurrentTimestamp(), Transaction().user],
                where=(move.snapshot == Null)
                & (move.post_date != Null)
                & move.period.in_([x.id for x in allowed_periods])))
        return snapshot.id


class LineAggregated(model.CoogSQL, model.CoogView):
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

    @classmethod
    def __setup__(cls):
        super(LineAggregated, cls).__setup__()
        cls._order.insert(0, ('snapshot', 'DESC'))
        cls._order.insert(1, ('create_date', 'DESC'))

    def get_currency_digits(self, name):
        return self.account.currency_digits

    @classmethod
    def get_tables(cls):
        pool = Pool()
        return {
            'account.move.line': pool.get('account.move.line'
                ).__table__(),
            'account.move': pool.get('account.move').__table__(),
            'account.journal': pool.get('account.journal').__table__()
            }

    @classmethod
    def where_clause(cls, tables):
        return None

    @classmethod
    def fields_to_select(cls, tables):
        line = tables['account.move.line']
        move = tables['account.move']
        journal = tables['account.journal']
        return [Max(line.id).as_('id'),
            Literal(0).as_('create_uid'),
            Literal(0).as_('create_date'),
            Literal(0).as_('write_uid'),
            Literal(0).as_('write_date'),
            Case((journal.aggregate,
                Literal('')),
                else_=Coalesce(Max(line.description),
                    Max(move.description))).as_('description'),
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
            ]

    @classmethod
    def get_group_by(cls, tables):
        line = tables['account.move.line']
        move = tables['account.move']
        journal = tables['account.journal']
        return [line.account,
            Case((journal.aggregate, move.journal), else_=line.id),
            journal.aggregate,
            move.journal,
            move.date,
            move.post_date,
            move.snapshot]

    @classmethod
    def join_table(cls, tables):
        line = tables['account.move.line']
        move = tables['account.move']
        journal = tables['account.journal']
        return line.join(move, condition=line.move == move.id
            ).join(journal, condition=move.journal == journal.id)

    @classmethod
    def table_query(cls):
        tables = cls.get_tables()
        return cls.join_table(tables).select(*cls.fields_to_select(tables),
            group_by=cls.get_group_by(tables),
            where=cls.where_clause(tables))


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
                domain_ = [
                    ('account', '=', line.account.id),
                    ('move.journal', '=', line.journal.id),
                    ('move.post_date', '=', line.post_date),
                    ('move.date', '=', line.date),
                    ]
                if line.snapshot:
                    domain_.append(('move.snapshot', '=', line.snapshot.id))
            else:
                domain_ = [('id', '=', l.id)]
            return domain_

        action['pyson_domain'] = ['OR'] + [domain(l) for l in lines]
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        return action, {}