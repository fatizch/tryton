# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA

__all__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)
        if product.clauses:
            result['clauses'] = [
                cls._describe_clause(x) for x in product.clauses]
        return result

    @classmethod
    def _describe_clause(cls, clause):
        return {
            'id': clause.id,
            'name': clause.name,
            'code': clause.code,
            'customizable': bool(clause.customizable),
            'content': clause.content,
            }

    @classmethod
    def _describe_product_schema(cls):
        schema = super()._describe_product_schema()
        schema['properties']['clauses'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._describe_clause_schema(),
            }
        return schema

    @classmethod
    def _describe_clause_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'id': OBJECT_ID_SCHEMA,
                'code': {'type': 'string'},
                'name': {'type': 'string'},
                'content': {'type': 'string'},
                'customizable': {'type': 'boolean'},
                },
            'required': ['id', 'name', 'code', 'customizable', 'content'],
            }

    @classmethod
    def _describe_products_examples(cls):
        examples = super()._describe_products_examples()
        examples[-1]['output'][-1]['clauses'] = [
            {
                'id': 1,
                'code': 'my_clause',
                'name': 'My Clause',
                'content': 'Whatever the clause content is',
                'customizable': False,
                },
            {
                'id': 2,
                'code': 'my_other_clause',
                'name': 'My Other Clause',
                'content': 'Pay everything to Mr. <NAME GOES HERE>',
                'customizable': True,
                },
            ]
        return examples
