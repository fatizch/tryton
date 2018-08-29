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
from trytond.model import Unique
from trytond.pyson import Eval, PYSONEncoder
from trytond.wizard import Wizard, StateView, StateTransition, StateAction, \
    Button
from trytond.transaction import Transaction
from trytond.server_context import ServerContext
from trytond.tools.multivalue import migrate_property
from trytond.modules.company.model import (CompanyValueMixin,
    CompanyMultiValueMixin)

from trytond.modules.coog_core import fields, model, utils
from trytond.model.multivalue import filter_pattern

__all__ = [
    'FiscalYear',
    'Journal',
    'Move',
    'Line',
    'Configuration',
    'ConfigurationSnapshotSequence',
    'Snapshot',
    'TakeSnapshot',
    'SnapshotStart',
    'SnapshotDone',
    'LineAggregated',
    'OpenLineAggregated',
    'OpenLine',
    ]


class FiscalYear:
    __metaclass__ = PoolMeta
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
    __metaclass__ = PoolMeta
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
    __metaclass__ = PoolMeta
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
        # Do not take snapshots for moves not in an exportable fiscal year
        moves_to_snapshot = [m for m in moves
            if m.period.fiscalyear.export_moves]
        move_groups = cls.group_moves_for_snapshots(moves_to_snapshot)
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
    __metaclass__ = PoolMeta
    __name__ = 'account.move.line'
    snapshot = fields.Function(fields.Many2One('account.move.snapshot',
            'Snapshot'), 'get_move_field', searcher='search_move_field')


class Configuration(CompanyMultiValueMixin):
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    snapshot_sequence = fields.MultiValue(fields.Many2One('ir.sequence',
            'Snapshot Sequence', required=True, domain=[
                ('code', '=', 'account.move.snapshot'),
                ]))

    @classmethod
    def default_snapshot_sequence(cls, **pattern):
        return cls.multivalue_model(
            'snapshot_sequence').default_snapshot_sequence(**pattern)


class ConfigurationSnapshotSequence(model.CoogSQL, CompanyValueMixin):
    'Account Configuration Snapshot Sequence'
    __name__ = 'account.configuration.snapshot_sequence'

    configuration = fields.Many2One('account.configuration', 'Configuration',
        ondelete='CASCADE', select=True)
    snapshot_sequence = fields.Many2One('ir.sequence',
        'Snapshot Sequence', domain=[('code', '=', 'account.move.snapshot')],
        ondelete='RESTRICT')

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        exist = TableHandler.table_exist(cls._table)
        super(ConfigurationSnapshotSequence, cls).__register__(module_name)
        if not exist:
            cls._migrate_property([], [], [])
        cls.update_snapshot_sequence_type()

    @classmethod
    def update_snapshot_sequence_type(cls):
        cursor = Transaction().connection.cursor()
        table = cls.__table__()
        sequence = Pool().get('ir.sequence').__table__()
        data_update = sequence.join(table, condition=(
                (sequence.id == table.snapshot_sequence) &
                (sequence.code == 'account.move'))).select(sequence.id)
        cursor.execute(*sequence.update(columns=[sequence.code],
                values=[Literal('account.move.snapshot')],
                from_=[data_update],
                where=data_update.id == sequence.id))

    @classmethod
    def _migrate_property(cls, field_names, value_names, fields):
        field_names.append('snapshot_sequence')
        value_names.append('snapshot_sequence')
        fields.append('company')
        migrate_property(
            'account.configuration', field_names, cls, value_names,
            parent='configuration', fields=fields)

    @classmethod
    def default_snapshot_sequence(cls, **pattern):
        Sequence = Pool().get('ir.sequence')
        pattern = filter_pattern(pattern, Sequence)
        domain = [('code', '=', 'account.move.snapshot')]
        for key, value in pattern.iteritems():
            domain.append((str(key), '=', value))
        sequences = Pool().get('ir.sequence').search(domain)
        if len(sequences) == 1:
            return sequences[0].id


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
    extracted = fields.Boolean('Extracted', readonly=True, select=True)

    @staticmethod
    def default_extracted():
        return False

    @classmethod
    def __setup__(cls):
        super(Snapshot, cls).__setup__()
        cls._error_messages.update({
            'no_sequence_defined': 'No sequence defined in configuration',
            'no_fiscal_year': 'No fiscal year defined with the Export Moves'
            ' option',
            })
        t = cls.__table__()
        cls._sql_constraints += [('snapshot_uniq_name', Unique(t, t.name),
                'The name on shapshot must be unique')]

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
    _rec_name = 'aggregated_move_id'

    aggregated_move_id = fields.Char('Aggregated Move Id', readonly=True)
    account = fields.Many2One('account.account', 'Account',
        ondelete='RESTRICT', readonly=True)
    journal = fields.Many2One('account.journal', 'Journal',
        ondelete='RESTRICT', readonly=True)
    date = fields.Date('Date', readonly=True)
    post_date = fields.Date('Post Date', readonly=True)
    snapshot = fields.Many2One('account.move.snapshot', 'Snapshot',
        ondelete='RESTRICT', readonly=True)
    debit = fields.Numeric('Debit', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    credit = fields.Numeric('Credit', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    currency_digits = fields.Function(fields.Integer('Currency Digits'),
        'get_currency_digits')
    description = fields.Char('Description', readonly=True)

    @classmethod
    def __setup__(cls):
        super(LineAggregated, cls).__setup__()
        cls._order = [
            ('snapshot', 'DESC'),
            ('post_date', 'DESC'),
            ('date', 'DESC'),
            ('aggregated_move_id', 'DESC'),
            ('journal', 'DESC'),
            ]

    def get_currency_digits(self, name):
        return self.account.currency_digits

    @classmethod
    def order_snapshot(cls, tables):
        table, _ = tables[None]
        return [table.snapshot]

    @classmethod
    def get_tables(cls):
        pool = Pool()
        return {
            'account.move.line': pool.get('account.move.line'
                ).__table__(),
            'account.move': pool.get('account.move').__table__(),
            'account.journal': pool.get('account.journal').__table__(),
            'account.move.snapshot': Pool().get('account.move.snapshot'
                ).__table__(),
            }

    @classmethod
    def where_clause(cls, tables):
        if not ServerContext().get('from_batch', None):
            return Literal(True)
        move = tables['account.move']
        snapshot = tables['account.move.snapshot']
        snap_ref = ServerContext().get('snap_ref', None)
        treatment_date = ServerContext().get('batch_treatment_date')
        if snap_ref:
            return (snapshot.name == snap_ref)
        return ((move.post_date <= treatment_date) &
            (snapshot.extracted == Literal(False)))

    @classmethod
    def sql_wrapper_batch(cls, col, type_):
        if ServerContext().get('from_batch', False):
            if type_ == 'date':
                return ToChar(col, 'YYYYMMDD')
            elif type_ == 'decimal':
                return Cast(col, 'VARCHAR')
        return col

    @classmethod
    def get_aggregate_prefix(cls):
        return ''

    @classmethod
    def get_move_prefix(cls):
        return ''

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
            Case((journal.aggregate and not journal.aggregate_posting,
                Literal('')),
                else_=Coalesce(Max(line.description),
                    Max(move.description))).as_('description'),
            Case((journal.aggregate,
                Concat(Concat(
                        cls.get_aggregate_prefix(),
                        ToChar(move.post_date, 'YYYYMMDD')),
                    Cast(move.snapshot, 'VARCHAR'))),
                else_=Concat(
                    cls.get_move_prefix(),
                    Max(move.number))).as_('aggregated_move_id'),
            line.account.as_('account'),
            move.journal.as_('journal'),
            cls.sql_wrapper_batch(move.date, 'date').as_('date'),
            cls.sql_wrapper_batch(move.post_date, 'date').as_('post_date'),
            move.snapshot.as_('snapshot'),
            cls.sql_wrapper_batch(Sum(Coalesce(line.debit, 0)), 'decimal').as_(
                'debit'),
            cls.sql_wrapper_batch(Sum(Coalesce(line.credit, 0)), 'decimal').as_(
                'credit'),
            ]

    @classmethod
    def get_group_by(cls, tables):
        line = tables['account.move.line']
        move = tables['account.move']
        journal = tables['account.journal']
        group_by = [line.account,
            Case((journal.aggregate, move.journal), else_=line.id),
            journal.aggregate,
            move.journal,
            move.date,
            move.post_date,
            move.snapshot,
            ]
        if ServerContext().get('from_batch', False):
            snapshot = tables['account.move.snapshot']
            group_by.append(snapshot.id)
        return group_by

    @classmethod
    def get_domain(cls, line):
        # Should return same filters as get_group_by
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
            domain_ = [('id', '=', line.id)]
        return domain_

    @classmethod
    def having_clause(cls, tables):
        line = tables['account.move.line']
        return (Sum(Coalesce(line.debit, 0)) -
                Sum(Coalesce(line.credit, 0)) != 0)

    @classmethod
    def join_table(cls, tables):
        line = tables['account.move.line']
        move = tables['account.move']
        journal = tables['account.journal']
        snapshot = tables['account.move.snapshot']
        query_table = line.join(move, condition=line.move == move.id
            ).join(journal, condition=move.journal == journal.id)
        if ServerContext().get('from_batch', False):
            query_table = query_table.join(snapshot, condition=(
                    move.snapshot == snapshot.id))
        return query_table

    @classmethod
    def get_order_by(cls, tables):
        move = tables['account.move']
        journal = tables['account.journal']
        snapshot = tables['account.move.snapshot']
        if ServerContext().get('from_batch', False):
            order = [snapshot.id.desc]
        else:
            order = []
        return order + [
            move.post_date.desc,
            move.date.desc,
            Case((journal.aggregate,
                Concat(Concat(
                        cls.get_aggregate_prefix(),
                        ToChar(move.post_date, 'YYYYMMDD')),
                    Cast(move.snapshot, 'VARCHAR'))),
                else_=Concat(
                    cls.get_move_prefix(),
                    Max(move.number))).as_('aggregated_move_id').desc,
            move.journal.desc,
            ]

    @classmethod
    def table_query(cls):
        tables = cls.get_tables()
        return cls.join_table(tables).select(*cls.fields_to_select(tables),
            group_by=cls.get_group_by(tables),
            where=cls.where_clause(tables),
            having=cls.having_clause(tables),
            order_by=cls.get_order_by(tables))


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

    def from_aggregate_model_name(self):
        return 'account.move.line.aggregated'

    def do_open_(self, action):
        pool = Pool()
        LineAggregated = pool.get(self.from_aggregate_model_name())
        lines = LineAggregated.browse(Transaction().context['active_ids'])
        action['pyson_domain'] = ['OR'] + [
            LineAggregated.get_domain(l) for l in lines]
        action['pyson_domain'] = PYSONEncoder().encode(action['pyson_domain'])
        return action, {}
