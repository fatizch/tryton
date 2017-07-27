# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
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
        Insurer = pool.get('insurer')
        domain = []
        template, = pool.get('report.template').search(
            [('code', '=', template)])
        if insurers:
            Party = pool.get('party.party')
            party_dom = [x.id for x in Party.search(
                    [('code', 'in', insurers.split(','))])]
            domain.append(('party', 'in', party_dom))
        if products:
            Product = pool.get('offered.product')
            product_dom = [x.id for x in Product.search(
                    [('code', 'in', products.split(','))])]
            domain.append(('product', 'in', product_dom))
        return [(x.id,) for x in Insurer.search(domain)]

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
