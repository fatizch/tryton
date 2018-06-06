# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os
import logging
import zipfile
import shutil

from sql import Literal, Null
from sql.aggregate import Sum
from sql.conditionals import Case
from itertools import groupby

from trytond.pool import Pool
from trytond.tools import grouped_slice
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch, coog_date, fields


__all__ = [
    'CreatePrestIjSubscription',
    'SubmitPrestIjSubscription',
    'ProcessPrestIjRequest',
    'ProcessGestipFluxBatch',
    ]


class BaseSelectPrestIj(batch.BatchRoot):

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.party'

    @classmethod
    def get_tables(cls, **kwargs):
        pool = Pool()
        party = pool.get('party.party').__table__()
        contract = pool.get('contract').__table__()
        product = pool.get('offered.product').__table__()
        coverage = pool.get('offered.product-option.description').__table__()
        benefit_rel = pool.get('option.description-benefit').__table__()
        benefit = pool.get('benefit').__table__()
        subscription = pool.get('claim.ij.subscription').__table__()
        return {
            'party.party': party,
            'contract': contract,
            'offered.product': product,
            'offered.product-option.description': coverage,
            'option.description-benefit': benefit_rel,
            'benefit': benefit,
            'claim.ij.subscription': subscription,
            }

    @classmethod
    def get_query_table(cls, tables, **kwargs):
        party = tables['party.party']
        contract = tables['contract']
        product = tables['offered.product']
        option_desc = tables['offered.product-option.description']
        benefit_rel = tables['option.description-benefit']
        benefit = tables['benefit']

        return contract.join(party,
            condition=(contract.subscriber == party.id)
            ).join(product,
                condition=(contract.product == product.id)
            ).join(option_desc,
                condition=(product.id == option_desc.product)
            ).join(benefit_rel,
                condition=(option_desc.coverage == benefit_rel.coverage)
            ).join(benefit,
                condition=(benefit_rel.benefit == benefit.id) &
                (benefit.prest_ij == Literal(True)))
        # TODO: Enhance performance with a subquery to filter contracts
        # 'contract.product.in_([x.id for x in products_subquery])'

    @classmethod
    def get_where_clause(cls, tables, **kwargs):
        party = tables['party.party']
        subscription = tables['claim.ij.subscription']
        operation = kwargs.get('operation', 'cre')
        Operator = fields.SQL_OPERATORS['=' if operation == 'cre' else '!=']
        sub_query = subscription.join(party, 'RIGHT OUTER', condition=(
                subscription.siren == party.siren)).select(party.id,
            where=Operator(subscription.id, Null))
        return party.id.in_(sub_query)

    @classmethod
    def select_ids(cls, **kwargs):
        tables = cls.get_tables(**kwargs)
        party = tables['party.party']

        cursor = Transaction().connection.cursor()
        cursor.execute(*cls.get_query_table(tables, **kwargs).select(party.id,
            where=cls.get_where_clause(tables, **kwargs)))
        return [(x,) for x in set([x[0] for x in cursor.fetchall()])]


class CreatePrestIjSubscription(BaseSelectPrestIj):
    'Create Prest Ij Susbscription'
    __name__ = 'prest_ij.subscription.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def execute(cls, objects, ids, treatment_date):
        Subscription = Pool().get('claim.ij.subscription')
        for sliced_objects in grouped_slice(objects):
            Subscription.create(
                [{'siren': siren}
                    for siren in list({x.siren for x in sliced_objects})])


class SubmitPrestIjSubscription(BaseSelectPrestIj):
    'Submit Prest Ij Susbscription'
    __name__ = 'prest_ij.subscription.submit'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'claim.ij.subscription'

    @classmethod
    def parse_params(cls, params):
        params = super(SubmitPrestIjSubscription, cls).parse_params(params)
        assert params.get('operation') in ('cre', 'sup'), 'Invalid operation'
        return params

    @classmethod
    def get_tables(cls, **kwargs):
        pool = Pool()
        tables = super(SubmitPrestIjSubscription, cls).get_tables(**kwargs)

        if 'claim.ij.subscription' not in tables:
            tables['claim.ij.subscription'] = pool.get(
                    'claim.ij.subscription').__table__()
        tables['claim.ij.subscription_request'] = pool.get(
            'claim.ij.subscription_request').__table__()
        return tables

    @classmethod
    def get_query_table(cls, tables, **kwargs):
        subscription = tables['claim.ij.subscription']
        request = tables['claim.ij.subscription_request']
        contract = tables['contract']
        party = tables['party.party']
        if kwargs['operation'] == 'cre':
            query_table = party.join(contract,
                condition=(contract.subscriber == party.id)
                ).join(subscription,
                    condition=(party.siren == subscription.siren))
        else:
            query_table = super(SubmitPrestIjSubscription, cls
                ).get_query_table(tables, **kwargs
                ).join(subscription,
                    condition=(party.siren == subscription.siren))
        return query_table.join(request, 'LEFT OUTER', condition=(
                request.subscription == subscription.id))

    @classmethod
    def get_where_clause(cls, tables, **kwargs):
        operation = kwargs.get('operation')
        subscription = tables['claim.ij.subscription']
        contract = tables['contract']
        if operation == 'cre':
            where_clause = (subscription.state == 'undeclared')
        else:
            where_clause = super(SubmitPrestIjSubscription, cls
                ).get_where_clause(tables, **kwargs)
            where_clause &= (subscription.state == 'declaration_confirmed')
            where_clause &= (contract.status == 'terminated')
        return where_clause

    @classmethod
    def get_having_clause(cls, tables, **kwargs):
        request = tables['claim.ij.subscription_request']
        operation = kwargs['operation']
        having_clause = Sum(Case((
                        (request.state == 'unprocessed') &
                        (request.operation == operation), 1), else_=0)
                ) == 0
        return having_clause

    @classmethod
    def select_ids(cls, treatment_date, operation):
        cursor = Transaction().connection.cursor()
        tables = cls.get_tables(treatment_date=treatment_date,
            operation=operation)
        subscription = tables['claim.ij.subscription']
        contract = tables['contract']
        query_table = cls.get_query_table(tables,
            treatment_date=treatment_date, operation=operation)
        where_clause = cls.get_where_clause(tables,
            treatment_date=treatment_date, operation=operation)
        cursor.execute(*query_table.select(subscription.id, contract.id,
                where=where_clause,
                having=cls.get_having_clause(tables,
                    treatment_date=treatment_date, operation=operation),
                group_by=[subscription.id, contract.id],
                order_by=[subscription.id, contract.id]
                ))

        for sub, contracts in groupby(cursor.fetchall(), key=lambda x: x[0]):
            contracts = [x[1] for x in contracts]
            if operation == 'cre':
                yield (sub, )
            else:
                contracts = Pool().get('contract').browse(contracts)
                date_to_check = max([c.end_date for c in contracts])
                if date_to_check < coog_date.add_year(treatment_date, -2):
                    yield (sub, )
                else:
                    continue
        # TODO: Handle BPIJ

    @classmethod
    def execute(cls, objects, ids, treatment_date, operation):
        Pool().get('claim.ij.subscription').create_subcription_requests(
            objects, operation, treatment_date)


class ProcessPrestIjRequest(batch.BatchRoot):
    'Process Prest Ij Subscription'
    __name__ = 'prest_ij.subscription.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(ProcessPrestIjRequest, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 0,
                'split': False,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'claim.ij.subscription_request'

    @classmethod
    def parse_params(cls, params):
        params = super(ProcessPrestIjRequest, cls).parse_params(params)
        assert 'output_dir' in params, 'output_dir is required'
        return params

    @classmethod
    def select_ids(cls, treatment_date, output_dir):
        cursor = Transaction().connection.cursor()
        request = Pool().get('claim.ij.subscription_request').__table__()
        cursor.execute(*request.select(request.id,
                where=request.state == 'unprocessed'))
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date, output_dir):
        Pool().get('claim.ij.subscription_request').process(objects,
            output_dir)


class ProcessGestipFluxBatch(batch.BatchRoot):
    'Process Gestip Flux Batch'
    __name__ = 'gestip.flux.process'

    logger = logging.getLogger(__name__)

    @classmethod
    def __setup__(cls):
        super(ProcessGestipFluxBatch, cls).__setup__()
        cls._default_config_items.update({'job_size': 1})

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return ids[:]

    @classmethod
    def parse_params(cls, params):
        params = super(ProcessGestipFluxBatch, cls).parse_params(params)
        params['kind'] = params['kind'].lower()
        assert params['kind'] in ('arl', 'cr'), 'Kind must be \'arl\' or \'cr\''
        return params

    @classmethod
    def select_ids(cls, treatment_date, directory, kind):
        for file_ in os.listdir(directory):
            if file_.endswith('.zip'):
                yield (os.path.join(directory, file_), )

    @classmethod
    def execute(cls, objects, ids, treatment_date, directory, kind):
        Group = Pool().get('claim.ij.subscription_request.group')
        archive_dir = os.path.join(directory, 'archive')
        if not os.path.exists(archive_dir):
            os.makedirs(archive_dir)
        for filepath in ids:
            to_archive = False
            zip_file = zipfile.ZipFile(filepath)
            for data_file in zip_file.namelist():
                with zip_file.open(data_file, 'r') as fd_:
                    data = fd_.read()
                    if not Group.get_file_kind(data).startswith(
                            '%s_data' % kind):
                        continue
                    process_method = getattr(Group, 'process_%s_data' % kind)
                    process_method(data)
                    to_archive = True
            if to_archive:
                shutil.move(filepath, archive_dir)
