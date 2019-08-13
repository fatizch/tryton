# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_coverage(cls, coverage):
        result = super()._describe_coverage(coverage)
        if coverage.beneficiaries_clauses:
            result['beneficiaries_clauses'] = [
                dict(default=coverage.default_beneficiary_clause.id == x.id,
                     **cls._describe_clause(x))
                for x in coverage.beneficiaries_clauses
                ]
        return result

    @classmethod
    def _describe_coverage_schema(cls):
        schema = super()._describe_coverage_schema()
        schema['properties']['beneficiaries_clauses'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._describe_clause_schema(),
            }
        return schema

    @classmethod
    def _describe_clause_schema(cls):
        schema = super()._describe_clause_schema()
        schema['properties']['default'] = {'type': 'boolean'}
        return schema

    @classmethod
    def _describe_products_examples(cls):
        examples = super()._describe_products_examples()
        examples[-1]['output'][-1]['coverages'][0]['beneficiaries_clauses'] = [
            {
                'id': 4,
                'code': 'my_beneficiary_clause',
                'name': 'My Beneficiary Clause',
                'content': 'Whatever the clause content is',
                'customizable': False,
                'default': True,
                },
            {
                'id': 5,
                'code': 'my_other_beneficiary_clause',
                'name': 'My Other Beneficiary Clause',
                'content': 'Pay everything to Mr. <NAME GOES HERE>',
                'customizable': True,
                'default': False,
                },
            ]
        return examples
