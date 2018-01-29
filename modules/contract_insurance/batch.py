# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
import logging

from trytond.modules.report_engine import batch as report_batch


__all__ = [
    'ContractDocumentRequestCreation',
    ]


class ContractDocumentRequestCreation(report_batch.ReportRequestCreationBatch):
    'Contract Document Request Creation Batch'

    __name__ = 'report_production.contract_request.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def parse_params(cls, params):
        new_params = super(ContractDocumentRequestCreation,
            cls).parse_params(params)
        if 'treatment_date' in params:
            new_params['treatment_date'] = datetime.datetime.strptime(
                params['treatment_date'], '%Y-%m-%d').date()
        return new_params

    @classmethod
    def get_batch_search_model(cls):
        return 'contract'

    @classmethod
    def get_batch_domain(cls, template, treatment_date=None, products=None,
            contract_ids=None, **template_args):
        domain = []
        if contract_ids:
            domain += [('id', 'in', [int(x) for x in contract_ids.split(',')])]
        if products:
            domain += [('product.code', 'in', products.split(','))]
        if treatment_date:
            domain += [
                ('activation_history', 'where', [
                        ('active', '=', True),
                        ('start_date', '<=', treatment_date)]),
                ('activation_history', 'where', [
                        ('active', '=', True),
                        ['OR',
                            ('end_date', '=', None),
                            ('end_date', '>=', treatment_date)]]),
                ]
        return domain

    @classmethod
    def execute(cls, objects, ids, template, treatment_date=None,
            products=None, contract_ids=None, **template_args):
        return super(ContractDocumentRequestCreation, cls).execute(
            objects, ids, template, **template_args)
