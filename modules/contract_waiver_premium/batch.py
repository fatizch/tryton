# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import logging
import datetime

from trytond.pool import Pool
from trytond.modules.coog_core import batch


__all__ = [
    'WaiverPeriodsCreationBatch',
    ]


class WaiverPeriodsCreationBatch(batch.BatchRoot):
    'Waiver Periods Creation Batch'

    __name__ = 'contract.waiver.create'

    logger = logging.getLogger(__name__)

    @classmethod
    def parse_params(cls, params):
        new_params = super(WaiverPeriodsCreationBatch,
            cls).parse_params(params)
        assert 'period_start' in params, 'Period start is required'
        assert 'period_end' in params, 'Period end is required'
        new_params['period_start'] = datetime.datetime.strptime(
            params['period_start'], '%Y-%m-%d').date()
        new_params['period_end'] = datetime.datetime.strptime(
            params['period_end'], '%Y-%m-%d').date()
        return new_params

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def get_batch_search_model(cls):
        return 'contract'

    @classmethod
    def get_batch_domain(cls, treatment_date, period_start, period_end,
            products=None, rebill=True, contract_ids=None):
        domain = [('status', 'in', ['active', 'hold', 'terminated'])]
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
                            ('end_date', '>=', period_start)]]),
                ]
        return domain

    @classmethod
    def execute(cls, objects, ids, treatment_date, period_start, period_end,
            products=None, rebill=True, contract_ids=None):
        Contract = Pool().get('contract')
        Contract.create_full_waiver_period(objects, period_start, period_end,
            rebill)
        cls.logger.info('%d waivers created' % len(objects))
