# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA, CODE_SCHEMA


__name__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)
        result['billing_configuration'] = {
            # Hack because order is not always set (though it should be)
            'billing_modes': [
                dict(sequence=idx, **cls._describe_billing_mode(x.billing_mode))
                for idx, x in enumerate(
                    product.billing_rules[0].ordered_billing_modes)],
            'billing_rule': bool(product.billing_rules[0].rule),
            }
        return result

    @classmethod
    def _describe_billing_mode(cls, billing_mode):
        return {
            'id': billing_mode.id,
            'name': billing_mode.name,
            'code': billing_mode.code,
            'frequency': billing_mode.frequency_string,
            'is_direct_debit': billing_mode.direct_debit,
            }

    @classmethod
    def _describe_product_schema(cls):
        schema = super()._describe_product_schema()
        schema['properties']['billing_configuration'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'billing_modes': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'id': OBJECT_ID_SCHEMA,
                            'code': CODE_SCHEMA,
                            'name': {'type': 'string'},
                            'frequency': {'type': 'string'},
                            'is_direct_debit': {'type': 'boolean'},
                            'sequence': {'type': 'integer'},
                            },
                        'required': ['id', 'code', 'name', 'frequency',
                            'is_direct_debit', 'sequence'],
                        },
                    },
                'billing_rule': {'type': 'boolean'},
                },
            'required': ['billing_modes', 'billing_rule'],
            }
        schema['required'].append('billing_configuration')
        return schema

    @classmethod
    def _describe_products_examples(cls):
        examples = super()._describe_products_examples()
        for example in examples:
            for description in example['output']:
                description['billing_configuration'] = {
                    'billing_modes': [
                        {
                            'id': 1,
                            'code': 'freq_yearly',
                            'name': 'Yearly (synced on 01/01)',
                            'frequency': 'Yearly',
                            'is_direct_debit': False,
                            'sequence': 0,
                            },
                        ],
                    'billing_rule': False,
                    }
        return examples
