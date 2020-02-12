# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.api import RATE_SCHEMA, amount_from_api
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.modules.party_cog.api import PARTY_RELATION_SCHEMA

__all__ = [
    'APIContract',
    ]


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _update_contract_parameters(cls, contract_data, created):
        super()._update_contract_parameters(contract_data, created)
        for covered in contract_data.get('covereds', []):
            for option in covered.get('coverages', []):
                if 'beneficiary_clause' in option:
                    for beneficiary in option['beneficiary_clause'].get(
                            'beneficiaries', []):
                        if ('party' in beneficiary and
                                'ref' in beneficiary['party']):
                            beneficiary['party'] = created['parties'][
                                beneficiary['party']['ref']]

    @classmethod
    def _create_option(cls, option_data, contract_data, created):
        option = super()._create_option(option_data, contract_data, created)

        if 'beneficiary_clause' in option_data:
            clause = option_data['beneficiary_clause']['clause']
            option.beneficiary_clause = clause
            if not clause.customizable:
                option.customized_beneficiary_clause = clause.content
            else:
                option.customized_beneficiary_clause = option_data[
                    'beneficiary_clause'].get('customized_text', clause.content)

            pool = Pool()
            Beneficiary = pool.get('contract.option.beneficiary')

            beneficiaries = []
            for benef_data in option_data['beneficiary_clause'].get(
                    'beneficiaries', []):
                beneficiary = Beneficiary()
                beneficiary.reference = benef_data.get('reference', '')
                beneficiary.share = benef_data['share']
                beneficiary.party = benef_data.get('party', None)

                # No way to properly reference an address in APIs for now
                beneficiary.accepting = False

                beneficiaries.append(beneficiary)

            option.beneficiaries = beneficiaries

        return option

    @classmethod
    def _contract_option_convert(cls, data, options, parameters, package=None,
            minimum=False):
        super()._contract_option_convert(data, options, parameters, package,
            minimum=minimum)

        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        coverage = data['coverage']
        if (coverage.beneficiaries_clauses and
                'beneficiary_clause' not in data):
            if coverage.default_beneficiary_clause:
                data['beneficiary_clause'] = {
                    'clause': {'code':
                        coverage.default_beneficiary_clause.code},
                    }
            elif len(coverage.beneficiaries_clauses) == 1:
                data['beneficiary_clause'] = {
                    'clause': {'code': coverage.beneficiaries_clauses[0].code},
                    }
            elif not minimum:
                API.add_input_error({
                        'type': 'missing_beneficiary_clause',
                        'data': {
                            'coverage': coverage.code,
                            },
                        })

        if 'beneficiary_clause' in data:
            allowed_beneficiary_clauses = {
                x.id for x in data['coverage'].beneficiaries_clauses}

            clause_data = data['beneficiary_clause']
            clause = API.instantiate_code_object('clause',
                clause_data['clause'])
            clause_data['clause'] = clause

            if clause.id not in allowed_beneficiary_clauses:
                API.add_input_error({
                        'type': 'unauthorised_beneficiary_clause',
                        'data': {
                            'coverage': coverage.code,
                            'clause': clause.code,
                            },
                        })

            if 'customized_text' in clause_data and not clause.customizable:
                API.add_input_error({
                        'type': 'non_customizable_clause',
                        'data': {
                            'clause': clause.code,
                            },
                        })

            for benef_data in data['beneficiary_clause'].get(
                    'beneficiaries', []):
                if 'party' not in benef_data and not benef_data['reference']:
                    API.add_input_error({
                            'type': 'missing_beneficiary_identification',
                            'data': {
                                'coverage': coverage.code,
                                },
                            })
                if 'party' in benef_data:
                    party = PartyAPI._party_from_reference(benef_data['party'],
                        parties=parameters['parties'])
                    if party:
                        benef_data['party'] = party
                benef_data['share'] = amount_from_api(benef_data['share'])

    @classmethod
    def _contract_option_schema(cls, minimum=False):
        schema = super()._contract_option_schema(minimum=minimum)
        schema['properties']['beneficiary_clause'] = {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'clause': CODED_OBJECT_SCHEMA,
                'customized_text': {'type': 'string'},
                'beneficiaries': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': cls._contract_beneficiary_schema(),
                    },
                },
            'required': ['clause'],
            }
        return schema

    @classmethod
    def _contract_beneficiary_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'party': PARTY_RELATION_SCHEMA,
                'reference': {'type': 'string'},
                'share': RATE_SCHEMA,
                },
            'required': ['share'],
            'anyOf': [
                {
                    'required': ['party'],
                    },
                {
                    'required': ['reference'],
                    },
                ],
            }
