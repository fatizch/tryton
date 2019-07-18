# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA


__name__ = [
    'APICore',
    'APIProduct',
    'APIParty',
    'APIContract',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _model_definitions_party(cls):
        definition = super()._model_definitions_party()
        definition['fields'].append(
            cls._field_description(
                'health.party_complement', 'hc_system', required=True,
                sequence=110, force_type='string'))
        definition['fields'].append(
            cls._field_description(
                'health.party_complement', 'insurance_fund',
                required=True, sequence=120, force_type='string'))
        return definition


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _describe_product(cls, product):
        result = super()._describe_product(product)

        if product.is_health and result['item_descriptors']:
            for item_desc in result['item_descriptors']:
                item_desc['fields']['required'] += ['hc_system',
                    'insurance_fund_number']
                item_desc['fields']['fields'] += ['hc_system',
                    'insurance_fund_number']

        return result


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _party_person_schema(cls):
        schema = super()._party_person_schema()
        schema['properties']['hc_system'] = CODED_OBJECT_SCHEMA
        schema['properties']['insurance_fund_number'] = {'type': 'string'}
        return schema

    @classmethod
    def _party_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')

        super()._party_convert(data, options, parameters)

        # The rules for the hc_system / fund_number relation are totally
        # unknown, so no nice validation here :'(
        if 'hc_system' in data:
            data['hc_system'] = API.instantiate_code_object(
                'health.care_system', data['hc_system'])
            if 'insurance_fund_number' not in data:
                API.add_input_error({
                        'type': 'missing_insurance_fund_number',
                        'data': {
                            'health_care_system': data['hc_system'].code,
                            },
                        })
        elif 'insurance_fund_number' in data:
            API.add_input_error({
                    'type': 'missing_healthcare_system',
                    'data': {
                        'insurance_fund_number': data['insurance_fund_number'],
                        },
                    })

    @classmethod
    def _update_party_complement(cls, party, data, options):
        super()._update_party_complement(party, data, options)

        complement = party.health_complement[-1]

        if 'hc_system' in data:
            complement.hc_system = data['hc_system']
            complement.insurance_fund_number = data['insurance_fund_number']


class APIContract(metaclass=PoolMeta):
    __name__ = 'api.contract'

    @classmethod
    def _check_contract_parameters_covereds(cls, data, contract_data):
        API = Pool().get('api')

        super()._check_contract_parameters_covereds(data, contract_data)

        if contract_data['product'].is_health:
            if not data['party'].health_complement[-1].hc_system:
                API.add_input_error({
                        'type': 'missing_healthcare_system',
                        'data': {
                            'field': 'covered.party',
                            },
                        })
