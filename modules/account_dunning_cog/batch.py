# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
from sql import Literal, Null

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'DunningUpdateBatch',
    'DunningCreationBatch',
    'DunningTreatmentBatch',
    ]


class DunningUpdateBatch(batch.BatchRoot):
    'Dunning Update Batch'
    __name__ = 'account.dunning.update'

    @classmethod
    def __setup__(cls):
        super(DunningUpdateBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.dunning'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.dunning'

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        pool = Pool()
        Dunning = pool.get('account.dunning')
        Dunning.update_dunnings(treatment_date)

    @classmethod
    def get_batch_args_name(cls):
        return ['']


class DunningCreationBatch(batch.BatchRoot):
    'Dunning Creation Batch'
    __name__ = 'account.dunning.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.move.line'

    @classmethod
    def get_models_for_query(cls):
        return ['account.move.line', 'account.dunning']

    @classmethod
    def get_tables(cls):
        pool = Pool()
        return {model_: pool.get(model_).__table__()
            for model_ in cls.get_models_for_query()}

    @classmethod
    def get_select_ids_query_table(cls, tables):
        Account = Pool().get('account.account')
        move_line = tables['account.move.line']
        accounts = [x.id for x in Account.search([('kind', '=', 'receivable')])]
        dunning = tables['account.dunning']
        return move_line.join(dunning, 'LEFT OUTER', condition=(
                (move_line.id == dunning.line) &
                (move_line.account.in_(accounts)))
            )

    @classmethod
    def get_where_clause(cls, tables, date):
        move_line = tables['account.move.line']
        dunning = tables['account.dunning']
        return ((move_line.maturity_date <= date) & (dunning.id == Null) & (
                (move_line.debit > 0) | (move_line.credit < 0)) &
            (move_line.party != Null) & (move_line.reconciliation == Null))

    @classmethod
    def get_having_clause(cls, tables):
        return (Literal(True))

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().connection.cursor()
        tables = cls.get_tables()
        query_table = cls.get_select_ids_query_table(tables)
        having_clause = cls.get_having_clause(tables)
        where_clause = cls.get_where_clause(tables, treatment_date)
        query = query_table.select(tables['account.move.line'].id,
            where=where_clause,
            group_by=[tables['account.move.line'].id],
            having=having_clause)
        cursor.execute(*query)
        res = cursor.fetchall()
        return res

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Dunning = Pool().get('account.dunning')
        Dunning._generate_dunnings(treatment_date, objects)
        cls.logger.info('Dunnings Generated Until %s' % treatment_date)


class DunningTreatmentBatch(batch.BatchRoot):
    'Process Dunning Batch'
    __name__ = 'account.dunning.treat'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'account.dunning'

    @classmethod
    def get_batch_search_model(cls):
        return 'account.dunning'

    @classmethod
    def get_batch_domain(cls):
        return [('state', '=', 'draft')]

    @classmethod
    def get_batch_ordering(cls):
        return [('level', 'DESC')]

    @classmethod
    def execute(cls, objects, ids):
        Dunning = Pool().get('account.dunning')
        Dunning.process(objects)
        cls.logger.info('Dunnings Process')
