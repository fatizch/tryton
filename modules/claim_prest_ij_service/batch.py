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
    'SubmitPersonPrestIjSubscription',
    'SubmitCompanyPrestIjSubscription',
    'ProcessPrestIjRequest',
    'ProcessGestipFluxBatch',
    ]


class BaseSelectPrestIj(batch.BatchRoot):

    @classmethod
    def get_batch_main_model_name(cls):
        return 'party.party'

    @classmethod
    def convert_to_instances(cls, ids, **kwargs):
        return ids[:]

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
        claim = pool.get('claim').__table__()
        service = pool.get('claim.service').__table__()
        loss = pool.get('claim.loss').__table__()
        loss_desc = pool.get('benefit.loss.description').__table__()

        return {
            'party.party': party,
            'party.party.company': pool.get('party.party').__table__(),
            'claim.ij.subscription.company':
            pool.get('claim.ij.subscription').__table__(),
            'contract': contract,
            'offered.product': product,
            'offered.product-option.description': coverage,
            'option.description-benefit': benefit_rel,
            'benefit': benefit,
            'claim.ij.subscription': subscription,
            'claim': claim,
            'claim.service': service,
            'claim.loss': loss,
            'benefit.loss.description': loss_desc,
             }

    @classmethod
    def get_query_table(cls, tables, **kwargs):
        party = tables['party.party']
        benefit = tables['benefit']
        contract = tables['contract']

        if kwargs['kind'] == 'company':
            product = tables['offered.product']
            option_desc = tables['offered.product-option.description']
            benefit_rel = tables['option.description-benefit']
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
        else:
            loss = tables['claim.loss']
            service = tables['claim.service']
            claim = tables['claim']
            loss_desc = tables['benefit.loss.description']
            company = tables['party.party.company']
            return loss.join(party, condition=(loss.covered_person == party.id)
                ).join(claim, condition=(loss.claim == claim.id)
                ).join(service, condition=(loss.id == service.loss)
                ).join(contract, condition=(service.contract == contract.id)
                ).join(company, condition=(contract.subscriber == company.id)
                ).join(benefit, condition=(service.benefit == benefit.id) &
                    (benefit.prest_ij == Literal(True))
                ).join(loss_desc, condition=(loss.loss_desc == loss_desc.id) &
                    (loss_desc.loss_kind == 'std')
                )

    @classmethod
    def get_where_clause(cls, tables, **kwargs):
        party = tables['party.party']
        company = tables['party.party.company']
        subscription = tables['claim.ij.subscription']
        operation = kwargs.get('operation', 'cre')
        Operator = fields.SQL_OPERATORS['=' if operation == 'cre' else '!=']
        if kwargs['kind'] == 'company':
            sub_query = subscription.join(party, 'RIGHT OUTER', condition=(
                    (subscription.siren == party.siren) &
                    (subscription.ssn == Null))).select(party.id,
                where=Operator(subscription.id, Null) &
                (party.is_person == Literal(False)))
        else:
            sub_query = subscription.join(party, 'RIGHT OUTER', condition=(
                    subscription.ssn == party.ssn)
                ).join(company, 'LEFT OUTER', condition=(
                    subscription.siren == company.siren)
                ).select(party.id,
                where=Operator(subscription.id, Null) &
                (party.is_person == Literal(True))
                )
        return party.id.in_(sub_query)

    @classmethod
    def select_ids(cls, **kwargs):
        tables = cls.get_tables(**kwargs)
        party = tables['party.party']
        company = tables['party.party.company']
        kind = kwargs['kind']

        cursor = Transaction().connection.cursor()
        to_select = (party.siren,) if kind == 'company' else (
            party.ssn, company.siren)
        cursor.execute(*cls.get_query_table(tables, **kwargs).select(
            *to_select, where=cls.get_where_clause(tables, **kwargs)))
        if kind == 'company':
            return [(x,) for x in {p for p, in cursor.fetchall()}]
        else:
            return [(x, siren)
                for x, siren in {(p, siren) for p, siren in cursor.fetchall()}]


class CreatePrestIjSubscription(BaseSelectPrestIj):
    'Create Prest Ij Susbscription'
    __name__ = 'prest_ij.subscription.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def parse_params(cls, params):
        params = super(CreatePrestIjSubscription, cls).parse_params(params)
        assert params.get('kind') in ('company', 'person'), 'Invalid kind'
        return params

    @classmethod
    def get_tables(cls, **kwargs):
        tables = super(CreatePrestIjSubscription, cls).get_tables(**kwargs)
        tables['contract.covered_element'] = Pool().get(
            'contract.covered_element').__table__()
        tables['contract.covered_element.population'] = Pool().get(
            'contract.covered_element').__table__()
        return tables

    @classmethod
    def get_query_table(cls, tables, **kwargs):
        if kwargs.get('kind') == 'company':
            return super(CreatePrestIjSubscription, cls).get_query_table(
                **kwargs)
        else:
            subscription = tables['claim.ij.subscription']
            company = tables['party.party.company']
            party = tables['party.party']
            contract = tables['contract']
            cov_elem = tables['contract.covered_element']
            population = tables['contract.covered_element.population']
            return cov_elem.join(party, condition=(
                    (cov_elem.party == party.id) & (cov_elem.parent != Null))
                ).join(population, condition=(cov_elem.parent == population.id)
                ).join(contract, condition=(population.contract == contract.id)
                ).join(company, condition=(contract.subscriber == company.id)
                ).join(subscription, condition=(
                        company.siren == subscription.siren) & (
                        subscription.activated == Literal(True)))

    @classmethod
    def execute(cls, objects, ids, treatment_date, kind):
        pool = Pool()
        Subscription = pool.get('claim.ij.subscription')
        for sliced_objects in grouped_slice(objects):
            if kind == 'company':
                values = [{'siren': siren}
                    for siren, in sliced_objects]
            else:
                values = [{
                        'siren': siren,
                        'ssn': ssn,
                        }
                    for ssn, siren in sliced_objects]
            Subscription.create(values)


class SubmitPersonPrestIjSubscription(BaseSelectPrestIj):
    'Submit Person Prest Ij Susbscription'
    __name__ = 'prest_ij.subscription.submit_person'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'claim.service'

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return Pool().get('claim.service').browse([x[0] for x in ids])

    @classmethod
    def get_tables(cls, **kwargs):
        pool = Pool()
        tables = super(SubmitPersonPrestIjSubscription, cls).get_tables(
            **kwargs)

        if 'claim.ij.subscription' not in tables:
            tables['claim.ij.subscription'] = pool.get(
                    'claim.ij.subscription').__table__()
        tables['claim.ij.subscription_request'] = pool.get(
            'claim.ij.subscription_request').__table__()
        tables['claim.ij.subscription.company'] = pool.get(
            'claim.ij.subscription').__table__()
        return tables

    @classmethod
    def parse_params(cls, params):
        params = super(SubmitPersonPrestIjSubscription, cls).parse_params(
            params)
        assert params.get('operation') in ('cre', 'sup'), 'Invalid operation'
        return params

    @classmethod
    def get_query_table(cls, tables, **kwargs):
        party = tables['party.party']
        claim = tables['claim']
        service = tables['claim.service']
        loss = tables['claim.loss']
        subscription = tables['claim.ij.subscription']
        request = tables['claim.ij.subscription_request']
        contract = tables['contract']
        company = tables['party.party.company']
        company_sub = tables['claim.ij.subscription.company']
        if kwargs['operation'] == 'cre':
            query_table = loss.join(party, condition=(
                    loss.covered_person == party.id)
                ).join(claim, condition=(
                    loss.claim == claim.id)
                ).join(service, condition=(
                    service.loss == loss.id)
                ).join(subscription,
                    condition=(party.ssn == subscription.ssn)
                ).join(contract,
                    condition=(service.contract == contract.id)
                ).join(company,
                    condition=(contract.subscriber == company.id)
                ).join(company_sub,
                    condition=(company.siren == company_sub.siren) &
                    (company_sub.ssn == Null) &
                    (company_sub.activated == Literal(True)) &
                    (company_sub.state == 'declaration_confirmed'))
        else:
            query_table = super(SubmitPersonPrestIjSubscription, cls
                ).get_query_table(tables, kind='person', **kwargs
                ).join(subscription,
                    condition=(party.ssn == subscription.ssn) &
                    (company.siren == subscription.siren))
        return query_table.join(request, 'LEFT OUTER', condition=(
            request.subscription == subscription.id))

    @classmethod
    def get_where_clause(cls, tables, **kwargs):
        operation = kwargs.get('operation')
        subscription = tables['claim.ij.subscription']
        loss = tables['claim.loss']
        claim = tables['claim']
        if operation == 'cre':
            claim = tables['claim']
            where_clause = (subscription.state == 'undeclared')
            where_clause &= (claim.status != 'closed')
        else:
            where_clause = super(SubmitPersonPrestIjSubscription, cls
                ).get_where_clause(tables, kind='person', **kwargs)
            where_clause &= (subscription.state == 'declaration_confirmed')
            where_clause &= (loss.end_date != Null)
            where_clause &= (claim.status != 'open')
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
        service = tables['claim.service']
        party = tables['party.party']
        company = tables['party.party.company']
        query_table = cls.get_query_table(tables,
            treatment_date=treatment_date, operation=operation)
        where_clause = cls.get_where_clause(tables,
            treatment_date=treatment_date, operation=operation)
        cursor.execute(*query_table.select(service.id,
                where=where_clause,
                having=cls.get_having_clause(tables,
                    treatment_date=treatment_date, operation=operation),
                group_by=[party.id, company.id, service.id],
                order_by=[party.id, company.id]))

        for service, in cursor.fetchall():
            if operation == 'cre':
                yield (service, )
            else:
                service = Pool().get('claim.service')(service)
                if service.loss.end_date < coog_date.add_month(
                        treatment_date, -2) and not any(x.status == 'open'
                        for x in service.loss.covered_person.claims):
                    yield (service.id, )
                else:
                    continue

    @classmethod
    def execute(cls, objects, ids, treatment_date, operation):
        Pool().get('claim.ij.subscription').create_subscription_requests(
            objects, operation, treatment_date, kind='person')


class SubmitCompanyPrestIjSubscription(BaseSelectPrestIj):
    'Submit Company Prest Ij Susbscription'
    __name__ = 'prest_ij.subscription.submit_company'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'claim.ij.subscription'

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return Pool().get('claim.ij.subscription').browse([x[0] for x in ids])

    @classmethod
    def parse_params(cls, params):
        params = super(SubmitCompanyPrestIjSubscription, cls).parse_params(
            params)
        assert params.get('operation') in ('cre', 'sup'), 'Invalid operation'
        return params

    @classmethod
    def get_tables(cls, **kwargs):
        pool = Pool()
        tables = super(SubmitCompanyPrestIjSubscription, cls).get_tables(
            **kwargs)

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
            query_table = super(SubmitCompanyPrestIjSubscription, cls
                ).get_query_table(tables, kind='company', **kwargs
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
            where_clause &= (subscription.ssn == Null)
        else:
            where_clause = super(SubmitCompanyPrestIjSubscription, cls
                ).get_where_clause(tables, kind='company', **kwargs)
            where_clause &= (subscription.state == 'declaration_confirmed')
            where_clause &= (contract.status == 'terminated')
            where_clause &= (subscription.ssn == Null)
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

        for sub, models in groupby(cursor.fetchall(), key=lambda x: x[0]):
            models = [x[1] for x in models]
            if operation == 'cre':
                yield (sub, )
            else:
                contracts = Pool().get('contract').browse(models)
                date_to_check = max([c.end_date for c in contracts])
                if date_to_check < coog_date.add_year(treatment_date, -2):
                    yield (sub, )
                else:
                    continue

    @classmethod
    def execute(cls, objects, ids, treatment_date, operation):
        Pool().get('claim.ij.subscription').create_subscription_requests(
            objects, operation, treatment_date, kind='company')


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
        assert params['kind'] in (
            'arl', 'cr'), 'Kind must be \'arl\' or \'cr\''
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
