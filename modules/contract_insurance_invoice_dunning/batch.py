# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Null
from sql.conditionals import Case, Coalesce
from sql.aggregate import Sum
from sql.functions import Abs

from trytond.pool import PoolMeta

__all__ = [
    'DunningCreationBatch',
    'DunningTreatmentBatch',
    ]


class DunningCreationBatch:
    __metaclass__ = PoolMeta
    __name__ = 'account.dunning.create'

    @classmethod
    def get_models_for_query(cls):
        return super(DunningCreationBatch, cls).get_models_for_query() + \
            ['account.payment']

    @classmethod
    def get_select_ids_query_table(cls, tables):
        payment = tables['account.payment']
        move_line = tables['account.move.line']
        return super(DunningCreationBatch, cls).get_select_ids_query_table(
            tables).join(payment, 'LEFT OUTER', condition=(
                    (move_line.id == payment.line)
                    & (payment.state != 'failed')))

    @classmethod
    def get_having_clause(cls, tables):
        payment = tables['account.payment']
        move_line = tables['account.move.line']
        payment_amount = Sum(Coalesce(payment.amount, 0))
        line_amount = Case((move_line.second_currency == Null,
                Abs(move_line.credit - move_line.debit) - payment_amount),
            else_=Abs(move_line.amount_second_currency))
        return (super(DunningCreationBatch, cls).get_having_clause(tables) &
            (line_amount > 0))


class DunningTreatmentBatch:
    __metaclass__ = PoolMeta
    __name__ = 'account.dunning.treat'

    @classmethod
    def get_batch_domain(cls):
        return super(DunningTreatmentBatch, cls).get_batch_domain() + [
            ('is_contract_main', '=', True)]
