# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql.conditionals import Coalesce, Case
from sql import Literal, Cast, Null
from sql.aggregate import Max, Sum
from sql.functions import ToChar
from sql.operators import Concat

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields
from trytond.modules.account_aggregate.account import LineAggregated, OpenLine

__all__ = [
    'Line',
    'AnalyticLineAggregated',
    'OpenAnalyticLine',
    ]


class Line:
    __metaclass__ = PoolMeta
    __name__ = 'analytic_account.line'

    snapshot = fields.Function(fields.Many2One('account.move.snapshot',
            'Snapshot'), 'getter_snapshot')

    @classmethod
    def getter_snapshot(cls, lines, name):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        analytic_line = cls.__table__()
        line = pool.get('account.move.line').__table__()
        move = pool.get('account.move').__table__()
        res = {x.id: None for x in lines}

        query = analytic_line.join(line, condition=(
                analytic_line.move_line == line.id) & (
                analytic_line.id.in_([x.id for x in lines]))
            ).join(move, condition=(
                line.move == move.id) & (move.snapshot != Null))
        cursor.execute(*query.select(analytic_line.id, move.snapshot))

        for analytic_line_id, snap_id in cursor.fetchall():
            res[analytic_line_id] = snap_id

        return res


class AnalyticLineAggregated(LineAggregated):
    'Analytic Line Aggregated'
    __name__ = 'analytic_account.line.aggregated'

    analytic_account = fields.Many2One('analytic_account.account',
        'Analytic Account', readonly=True)

    @classmethod
    def get_tables(cls):
        tables = super(AnalyticLineAggregated, cls).get_tables()
        tables['analytic_account.line'] = Pool().get('analytic_account.line'
            ).__table__()
        return tables

    @classmethod
    def fields_to_select(cls, tables):
        analytic_line = tables['analytic_account.line']
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
            analytic_line.account.as_('analytic_account'),
            move.journal.as_('journal'),
            cls.sql_wrapper_batch(move.date, 'date').as_('date'),
            cls.sql_wrapper_batch(move.post_date, 'date').as_('post_date'),
            move.snapshot.as_('snapshot'),
            cls.sql_wrapper_batch(Sum(Coalesce(analytic_line.debit, 0)),
                'decimal').as_('debit'),
            cls.sql_wrapper_batch(Sum(Coalesce(analytic_line.credit, 0)),
                'decimal').as_('credit'),
            ]

    @classmethod
    def join_table(cls, tables):
        analytic_line = tables['analytic_account.line']
        line = tables['account.move.line']
        query_table = super(AnalyticLineAggregated, cls).join_table(tables)
        return analytic_line.join(query_table, condition=(
                analytic_line.move_line == line.id))

    @classmethod
    def get_group_by(cls, tables):
        analytic_line = tables['analytic_account.line']
        group_by = super(AnalyticLineAggregated, cls).get_group_by(tables)
        return group_by + [analytic_line.account]

    @classmethod
    def having_clause(cls, tables):
        analytic_line = tables['analytic_account.line']
        return (Sum(Coalesce(analytic_line.debit, 0)) -
                Sum(Coalesce(analytic_line.credit, 0)) != 0)

    @classmethod
    def get_domain(cls, analytic_line):
        # Should return same filters as get_group_by
        domain_ = super(AnalyticLineAggregated, cls).get_domain(analytic_line)
        # Not sure about that ?
        if analytic_line.journal.aggregate:
            domain_.append(
                ('analytic_lines.account', '=',
                    analytic_line.analytic_account.id))
        return domain_


class OpenAnalyticLine(OpenLine):
    'Open Analytic Line'
    __name__ = 'analytic_account.line.aggregated.open_line'

    def from_aggregate_model_name(self):
        return 'analytic_account.line.aggregated'
