# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import DEFAULT_INPUT_SCHEMA
from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA, CODE_SCHEMA
from trytond.modules.coog_core.api import OBJECT_ID_NULL_SCHEMA
from trytond.modules.offered.api import CONTRACT_PARTY_SCHEMA


__all__ = [
    'APIProduct',
    ]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def __post_setup__(cls):
        super().__post_setup__()

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)
        result['item_descriptors'] = [
            cls._describe_item_descriptor(x) for x in product.item_descriptors]
        if product.packages:
            result['covered_packages'] = bool(
                product.packages_defined_per_covered)
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
            'party': {
                'model': 'party',
                'domains': cls._get_covered_party_domains(item_desc)
                } if item_desc.kind else {},
            }

    @classmethod
    def _init_covered_party_domains(cls):
        # The keys of this represent a context
        # and the values are dictionnaries with named domains as keys
        domains = {
            'quotation': {},
            'subscription': {},
            }
        return domains

    @classmethod
    def _get_covered_party_domains(cls, item_desc):
        domains = cls._init_covered_party_domains()
        cls._update_covered_party_domains_from_item_desc(item_desc, domains)
        domain_descriptions = cls._format_party_domains(domains)
        return domain_descriptions

    @classmethod
    def _update_covered_party_domains_from_item_desc(cls, item_desc, domains):
        person_conditions = [
            {'name': 'is_person', 'operator': '=', 'value': True}]
        company_conditions = [
            {'name': 'is_person', 'operator': '=', 'value': False}]

        person_quotation_domain = {
            'conditions': list(person_conditions),
            'fields': [
                {'code': 'birth_date', 'required': True}
                ],
            }

        company_quotation_domain = {
            'conditions': list(company_conditions),
            'fields': [],
            }

        person_subscription_domain = {
            'conditions': list(person_conditions),
            'fields': [
                {'code': 'addresses', 'required': True},
                {'code': 'birth_date', 'required': True},
                {'code': 'email', 'required': False},
                {'code': 'first_name', 'required': True},
                {'code': 'is_person', 'required': False},
                {'code': 'name', 'required': True},
                {'code': 'phone', 'required': False},
                ]
            }

        company_subscription_domain = {
            'conditions': list(company_conditions),
            'fields': [
                {'code': 'addresses', 'required': True},
                {'code': 'email', 'required': False},
                {'code': 'is_person', 'required': False},
                {'code': 'name', 'required': True},
                {'code': 'phone', 'required': False},
                ]
            }

        if item_desc.kind == 'person':
            domains['quotation']['person_domain'] = person_quotation_domain
            domains['subscription']['person_domain'] = \
                person_subscription_domain
        elif item_desc.kind == 'company':
            domains['quotation']['company_domain'] = company_quotation_domain
            domains['subscription']['company_domain'] = \
                company_subscription_domain
        elif item_desc.kind == 'party':
            domains['quotation']['person_domain'] = person_quotation_domain
            domains['quotation']['company_domain'] = company_quotation_domain
            domains['subscription']['person_domain'] = \
                person_subscription_domain
            domains['subscription']['company_domain'] = \
                company_subscription_domain
        else:
            raise NotImplementedError

    @classmethod
    def _describe_product_schema(cls):
        schema = super()._describe_product_schema()
        schema['properties']['item_descriptors'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._describe_item_descriptor_schema(),
            }
        schema['properties']['covered_packages'] = {'type': 'boolean'}
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
                'party': {
                    'oneOf': [CONTRACT_PARTY_SCHEMA, DEFAULT_INPUT_SCHEMA],
                    },
                },
            'required': ['id', 'code', 'name', 'extra_data', 'party'],
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
                        'party': {
                            'model': 'party',
                            'domains': {
                                'quotation': [{
                                    'conditions': [],
                                    'fields': []
                                    }],
                                'subscription': [{
                                    'conditions': [],
                                    'fields': []
                                    }],
                                }
                            }
                        },
                    ]
                for coverage in description['coverages']:
                    coverage['item_desc'] = 1
        return examples
