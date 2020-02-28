# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.modules.coog_core import batch

__all__ = [
    'CalculatePremiumsBatch',
    'CreateInvoiceContractBatch',
    ]


class CalculatePremiumsBatch(batch.BatchRoot):
    'Calculate Premiums Batch'

    __name__ = 'contract.premium.calculate'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._default_config_items.update({
                'split': True,
                'job_size': 100,
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract'

    @classmethod
    def get_batch_search_model(cls):
        return 'contract'

    @classmethod
    def get_batch_domain(cls, treatment_date, **kwargs):
        domain = [('status', '!=', 'void')]
        if treatment_date:
            domain += [('premium_validity_end', '>', treatment_date)]
            domain += [
                ('activation_history', 'where', [
                        ('active', '=', True),
                        ('start_date', '<', treatment_date),
                        ['OR',
                            ('end_date', '=', None),
                            ('end_date', '>', treatment_date)
                        ]]),
                ]
        return domain

    @classmethod
    def execute(cls, objects, ids, treatment_date, from_date):
        from_date = datetime.datetime.strptime(from_date, '%Y-%m-%d').date()
        Contract = Pool().get('contract')

        with Transaction().set_context(client_defined_date=treatment_date):
            Contract.update_premium_validity_date(objects)
        Contract.calculate_prices(objects, from_date)


class CreateInvoiceContractBatch(metaclass=PoolMeta):
    __name__ = 'contract.invoice.create'

    @classmethod
    def _select_ids_where_clause(cls, tables, treatment_date):
        return((super()._select_ids_where_clause(tables, treatment_date))
            & (tables['contract'].premium_validity_end > treatment_date))
