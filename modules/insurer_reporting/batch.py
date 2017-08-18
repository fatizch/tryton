# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Literal

from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.modules.coog_core import batch


__all__ = [
    'InsurerReportContractBatch',
    ]


class InsurerReportContractBatch(batch.BatchRoot):
    'Insurer Report Contract Batch'

    __name__ = 'insurer_reporting.contract.generate'

    @classmethod
    def __setup__(cls):
        super(InsurerReportContractBatch, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 1,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'insurer'

    @classmethod
    def parse_params(cls, params):
        params = super(InsurerReportContractBatch, cls).parse_params(params)
        assert params['job_size'] == 1, 'Job size for this batch must be 1'
        return params

    @classmethod
    def select_ids(cls, treatment_date, template, insurers=None,
            products=None, possible_days=None):
        possible_days = possible_days.split(',') if possible_days else []
        if possible_days and not str(treatment_date.day) in possible_days:
            return []
        pool = Pool()
        cursor = Transaction().connection.cursor()
        product_table = pool.get('offered.product').__table__()
        coverage_table = pool.get('offered.option.description').__table__()
        product_coverage_table = pool.get(
            'offered.product-option.description').__table__()
        insurer_table = pool.get('insurer').__table__()
        party_table = pool.get('party.party').__table__()
        where_clause = Literal(True)

        if insurers:
            where_clause &= party_table.name.in_(insurers.split(','))
        if products:
            where_clause &= product_table.code.in_(products.split(','))

        query = insurer_table.join(coverage_table,
            condition=(coverage_table.insurer == insurer_table.id)
            ).join(product_coverage_table,
            condition=(product_coverage_table.coverage == coverage_table.id)
            ).join(product_table,
            condition=(product_coverage_table.product == product_table.id)
            ).join(party_table,
            condition=(insurer_table.party == party_table.id)
            ).select(insurer_table.id,
               where=where_clause)
        cursor.execute(*query)
        return cursor.fetchall()

    @classmethod
    def execute(cls, objects, ids, treatment_date, template, insurers=None,
            products=None, possible_days=None):
        pool = Pool()
        InsurerReportWizard = pool.get('insurer_reporting.contract',
            type='wizard')
        template, = pool.get('report.template').search(
            [('code', '=', template)])
        wizard_id, _, _ = InsurerReportWizard.create()
        create_reports = InsurerReportWizard(wizard_id)
        create_reports.configure_report.insurer = objects[0]
        create_reports.configure_report.template = template
        create_reports.configure_report.at_date = treatment_date
        create_reports.default_result(None)
        return ids
