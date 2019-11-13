# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import DATE_SCHEMA, AMOUNT_SCHEMA
from trytond.modules.api.api.core import date_from_api


__all__ = [
    'APIParty',
    ]


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _party_employment_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'entry_date': DATE_SCHEMA,
                'employment_kind': {'type': 'string'},
                'gross_salary': AMOUNT_SCHEMA,
            },
            'required': ['entry_date'],
        }

    @classmethod
    def _party_person_schema(cls):
        schema = super()._party_person_schema()
        schema['properties']['employments'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._party_employment_schema(),
            'minItems': 1,
            }
        return schema

    @classmethod
    def _init_new_person(cls, data, options):
        party = super()._init_new_person(data, options)
        party.employments = []
        return party

    @classmethod
    def _party_employment_convert(cls, data, options, parameters):
        data['entry_date'] = date_from_api(data['entry_date'])
        data['start_date'] = data['entry_date']
        data['employment_kind'] = Pool().get('api').instance_from_code(
            'party.employment_kind', data['employment_kind'])

    @classmethod
    def _party_convert(cls, data, options, parameters):
        super()._party_convert(data, options, parameters)
        for employment in data.get('employments', []):
            cls._party_employment_convert(employment, options, parameters)

    @classmethod
    def _update_person(cls, party, data, options):
        super()._update_person(party, data, options)
        cls._update_party_employment(party, data, options)

    @classmethod
    def _create_version(cls, data):
        Version = Pool().get('party.employment.version')
        version = Version()
        version.date = data['entry_date']
        if data.get('gross_salary'):
            version.gross_salary = data['gross_salary']
        return version

    @classmethod
    def _new_party_employment(cls, data):
        Employment = Pool().get('party.employment')
        employment = Employment()
        employment.entry_date = data['entry_date']
        employment.start_date = data['start_date']
        employment.employment_kind = data['employment_kind']
        employment.versions = [cls._create_version(data)]
        return employment

    @classmethod
    def _update_party_employment(cls, party, data, options):
        Pool().get('party.employment').delete(party.employments)
        new_employments = []
        for employment_data in data.get('employments', []):
            new_employments.append(cls._new_party_employment(
                employment_data))
        party.employments = new_employments

    @classmethod
    def _create_party_examples(cls):
        example_party_employment = {
            'input': {
                'parties': [{
                    'ref': '5',
                    'is_person': True,
                    'name': 'Doe',
                    'first_name': 'Daisy',
                    'birth_date': '1974-06-10',
                    'gender': 'female',
                    'employments': [{
                        'entry_date': '2012-05-05',
                        'employment_kind': 'test',
                        'gross_salary': '10000',
                        }]
                    },
                    ],
                },
            'output': {
                'parties': [{'ref': '5', 'id': 1}],
                },
            }
        return super()._create_party_examples() + [example_party_employment]


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _update_covered_party_domains_from_item_desc(cls, item_desc, domains):
        super()._update_covered_party_domains_from_item_desc(item_desc, domains)
        if item_desc.kind == 'person' and item_desc.employment_required:
            domains['subscription']['person_domain']['fields'].append(
                {'code': 'employments', 'required': True})
            domains['quotation']['person_domain']['fields'].append(
                {'code': 'employments', 'required': True})
