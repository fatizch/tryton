# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import FIELD_SCHEMA


__all__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        pool = Pool()
        ApiCore = pool.get('api.core')
        ExtraData = pool.get('extra_data')
        result = super()._describe_product(product)
        if product.is_loan:
            result['loan_configuration'] = {
                'fields': cls._describe_loan(),
                'extra_data': ApiCore._extra_data_structure(
                    ExtraData.search([('kind', '=', 'loan')])),
                }
        return result

    @classmethod
    def _describe_loan(cls):
        Core = Pool().get('api.core')
        return [
            Core._field_description('loan', 'amount',
                required=True, sequence=10),
            Core._field_description('loan', 'kind',
                required=True, sequence=20),
            Core._field_description('loan', 'payment_frequency',
                required=True, sequence=30),
            Core._field_description('loan', 'rate',
                required=True, sequence=40),
            Core._field_description('loan', 'funds_release_date',
                required=True, sequence=50),
            Core._field_description('loan', 'first_payment_date',
                required=False, sequence=60),
            Core._field_description('loan', 'duration',
                required=True, sequence=70),
            Core._field_description('loan', 'duration_unit',
                required=True, sequence=80),
            Core._field_description('loan', 'deferral',
                required=False, sequence=90),
            Core._field_description('loan', 'deferral_duration',
                required=False, sequence=100),
            ]

    @classmethod
    def _describe_product_schema(cls):
        result = super()._describe_product_schema()
        result['properties']['loan_configuration'] = \
            cls._describe_loan_schema()
        return result

    @classmethod
    def _describe_loan_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'fields': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': FIELD_SCHEMA,
                    },
                'extra_data': Pool().get('api.core')._extra_data_schema(),
                },
            }
