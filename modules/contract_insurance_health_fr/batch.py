# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from sql import Literal

from trytond.tools import grouped_slice
from trytond.pool import Pool

from trytond.modules.report_engine import batch


__all__ = [
    'MadelinLawReport',
    ]


class MadelinLawReport(batch.GenerateReportPeriod):
    'Madelin Law Report Batch'

    __name__ = 'madelin.law.report'

    @classmethod
    def parse_params(cls, params):
        params['on_model'] = 'contract'
        params = super(MadelinLawReport, cls).parse_params(params)
        return params

    @classmethod
    def _get_tables(cls, **kwargs):
        pool = Pool()
        tables = super(MadelinLawReport, cls)._get_tables(**kwargs)
        tables['party.party'] = pool.get('party.party').__table__()
        tables['contract.activation_history'] = pool.get(
            'contract.activation_history').__table__()
        tables['offered.product'] = pool.get('offered.product').__table__()
        tables['health.party_complement'] = pool.get('health.party_complement'
            ).__table__()
        tables['health.care_system'] = pool.get('health.care_system'
            ).__table__()
        return tables

    @classmethod
    def _get_query_table(cls, tables, **kwargs):
        query_table = super(MadelinLawReport, cls)._get_query_table(tables,
            **kwargs)
        activation_history = tables['contract.activation_history']
        product = tables['offered.product']
        contract = tables['contract']
        return query_table.join(product, condition=(
                contract.product == product.id)).join(
                activation_history, condition=(
                        activation_history.contract == contract.id))

    @classmethod
    def _get_where_clause(cls, tables, **kwargs):
        activation_history = tables['contract.activation_history']
        start_date = kwargs['from_date']
        end_date = kwargs['to_date']
        product = tables['offered.product']

        return super(MadelinLawReport, cls)._get_where_clause(tables,
            **kwargs) & ((activation_history.end_date > start_date) & (
                    activation_history.start_date < end_date)
                    ) & (product.print_madelin_reports == Literal(True))

    @classmethod
    def _filter_query_ids(cls, selection, **kwargs):
        Contract = Pool().get('contract')
        ids = list({x for x, in selection})
        for sub_ids in grouped_slice(ids):
            grouped_contracts = Contract.browse(sub_ids)
            for contract in grouped_contracts:
                if not contract.subscriber.social_security_dependent and \
                        contract._get_rsi_invoices(kwargs['from_date'],
                        kwargs['to_date'], invoice_state='paid'):
                    yield (contract.id,)
                else:
                    continue
