# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA, CODE_SCHEMA
from trytond.modules.coog_core.api import FIELD_SCHEMA, OBJECT_ID_NULL_SCHEMA


__name__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)
        result['item_descriptors'] = [
            cls._describe_item_descriptor(x) for x in product.item_descriptors]
        return result

    @classmethod
    def _describe_coverage(cls, coverage):
        result = super()._describe_coverage(coverage)
        result['item_desc'] = (coverage.item_desc.id
            if coverage.item_desc else None)
        return result

    @classmethod
    def _describe_item_descriptor(cls, item_desc):
        pool = Pool()
        ApiCore = pool.get('api.core')
        return {
            'id': item_desc.id,
            'code': item_desc.code,
            'name': item_desc.name,
            'extra_data': ApiCore._extra_data_structure(
                item_desc.extra_data_def),
            'fields': cls._describe_item_descriptor_fields(item_desc),
            }

    @classmethod
    def _describe_item_descriptor_fields(cls, item_desc):
        Core = Pool().get('api.core')
        if not item_desc.kind:
            return []
        if item_desc.kind == 'person':
            return Core._person_description(
                with_birth_date=True,
                with_birth_date_required=True,
                )
        if item_desc.kind == 'company':
            return Core._company_description()
        if item_desc.kind == 'party':
            return Core._party_description(
                with_birth_date=True,
                with_birth_date_required=True,
                )
        raise NotImplementedError

    @classmethod
    def _describe_product_schema(cls):
        schema = super()._describe_product_schema()
        schema['properties']['item_descriptors'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._describe_item_descriptor_schema(),
            }
        schema['required'].append('item_descriptors')
        return schema

    @classmethod
    def _describe_coverage_schema(cls):
        schema = super()._describe_coverage_schema()
        schema['properties']['item_desc'] = OBJECT_ID_NULL_SCHEMA
        schema['required'].append('item_desc')
        return schema

    @classmethod
    def _describe_item_descriptor_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': CODE_SCHEMA,
                'name': {'type': 'string'},
                'extra_data': Pool().get('api.core')._extra_data_schema(),
                'fields': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': FIELD_SCHEMA,
                    },
                },
            'required': ['id', 'code', 'name', 'extra_data', 'fields'],
            }

    @classmethod
    def _describe_products_examples(cls):
        examples = super()._describe_products_examples()
        for example in examples:
            for description in example['output']:
                description['item_descriptors'] = [
                    {
                        'id': 1,
                        'code': 'item_desc_1',
                        'name': 'Item Descriptor 1',
                        'extra_data': [],
                        'fields': [],
                        },
                    ]
                for coverage in description['coverages']:
                    coverage['item_desc'] = 1
        return examples
