# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging

from sql import Literal, Window, Null, Cast
from sql.conditionals import Coalesce, Greatest, Case
from sql.aggregate import Max

from collections import OrderedDict

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import batch


__all__ = [
    'ContractEndDateTerminationBatch',
    'PartyAnonymizeIdentificationBatch',
    'TerminateContractOption',
    ]


class ContractEndDateTerminationBatch(batch.BatchRoot):
    'Contract end date termination batch'

    __name__ = 'contract.termination.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def select_ids(cls, treatment_date):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        contract = pool.get('contract').__table__()
        activation_history = pool.get('contract.activation_history'
            ).__table__()
        win_query = activation_history.select(
            activation_history.contract,
            activation_history.active,
            Coalesce(activation_history.end_date,
                datetime.date.max).as_('end_date'),
            Max(Coalesce(activation_history.end_date, datetime.date.max),
                window=Window([activation_history.contract])).as_('max_end'),
            where=(activation_history.active == Literal(True)))
        cursor.execute(*contract.join(win_query,
                condition=win_query.contract == contract.id
                ).select(contract.id,
                    where=(contract.status.in_(['active', 'hold'])
                        & (win_query.end_date == win_query.max_end)
                        & (win_query.end_date < treatment_date))))
        return [x for x in cursor.fetchall()]

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Contract = Pool().get('contract')
        Contract.do_terminate(objects)
        cls.logger.info('Terminated %d contracts.' % len(objects))


class PartyAnonymizeIdentificationBatch(batch.BatchRoot):
    'Identify Parties to Anonymize batch'

    __name__ = 'party.anonymize.identify'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(PartyAnonymizeIdentificationBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                })

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return []

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.party'

    @classmethod
    def get_tables(cls):
        pool = Pool()
        activation_history = pool.get('contract.activation_history').__table__()
        win_query = activation_history.select(
            activation_history.contract,
            activation_history.active,
            Coalesce(activation_history.write_date,
                activation_history.create_date).as_('update_date'),
            activation_history.end_date,
            Max(Coalesce(activation_history.end_date, datetime.date.max),
                window=Window([activation_history.contract])).as_('max_end'),
            where=((activation_history.active == Literal(True)) &
                (activation_history.end_date != Null)))
        res = OrderedDict({})
        contract = pool.get('contract').__table__()
        res['contract'] = {
            'table': contract,
            'condition': None}
        res['activation_history'] = {
            'table': win_query,
            'condition': (res['contract']['table'].id == win_query.contract)}
        party = pool.get('party.party').__table__()
        res['party'] = {
            'table': party,
            'condition': (res['contract']['table'].subscriber == party.id)}
        return res

    @classmethod
    def get_where_clause(cls, tables, treatment_date):
        # getting unanonymized parties that are subscribers of terminated
        # contracts. Those contracts must have:
        # max(final_end_date, activation_history write date) + data shelf life
        # inferior to treatment_date
        contract = tables['contract']['table']
        activation_history = tables['activation_history']['table']
        party = tables['party']['table']
        Product = Pool().get('offered.product')
        products = Product.search([('data_shelf_life', '!=', Null)])
        case = Case(*[(contract.product == x.id,
                    str(x.data_shelf_life) + ' year')
                for x in products])
        return ((contract.status == 'terminated')
            & (contract.product.in_([x.id for x in products]))
            & (activation_history.end_date == activation_history.max_end)
            & (party.is_anonymized == Literal(False))
            & (party.planned_anonymisation_date != Null)
            & ((Greatest(activation_history.max_end,
                        activation_history.update_date) + Cast(case, 'interval')
                <= treatment_date)))

    @classmethod
    def get_query_table(cls, tables):
        res = None
        for table in tables:
            if res is None:
                res = tables[table]['table']
            else:
                res = tables[table]['table'].join(res,
                    condition=tables[table]['condition'])
        return res

    @classmethod
    def select_ids(cls, treatment_date):
        cursor = Transaction().connection.cursor()
        tables = cls.get_tables()
        party = tables['party']['table']
        query_table = cls.get_query_table(tables)
        cursor.execute(*query_table.select(party.id,
            where=cls.get_where_clause(tables, treatment_date)))
        return list(set(cursor.fetchall()))

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        party = Pool().get('party.party').__table__()
        cursor = Transaction().connection.cursor()
        cursor.execute(*party.update(
                columns=[party.planned_anonymisation_date],
                values=[treatment_date],
                where=party.id.in_(ids)))
        cls.logger.info('%d parties identified to be anonymized' % len(objects))


class TerminateContractOption(batch.BatchRoot):
    "Terminate Contract Option"

    __name__ = 'contract.option.terminate'
    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(TerminateContractOption, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 50,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract.option'

    @classmethod
    def get_batch_search_model(cls):
        return 'contract.option'

    @classmethod
    def get_batch_domain(cls, treatment_date):
        # First OR clause is for contract options whose automatic end date
        # is exceeded. Theses options are active, a manual end date defined and
        # a coverage with an ending rule.
        # The second OR clause is for contract options whose manual end '
        # date is exceeded and already have a termination sub status.
        return ['OR',
            [
                ('coverage.ending_rule', '!=', None),
                ('automatic_end_date', '!=', None),
                ('automatic_end_date', '<', treatment_date),
                ('status', '=', 'active'),
                ],
            [
                ('manual_end_date', '<', treatment_date),
                ('status', '=', 'active'),
                ],
            ]

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Pool().get('contract.option').automatic_terminate(objects)
        return ids
