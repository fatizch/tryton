# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.exceptions import UserError


__name__ = [
    'APICore',
    'APIParty',
    'APIProduct',
    ]


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _model_definitions_party(cls):
        definition = super()._model_definitions_party()
        definition['fields'].append(cls._field_description(
                'party.party', 'ssn', required=False, sequence=100))
        return definition


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _party_person_schema(cls):
        schema = super()._party_person_schema()
        schema['properties']['ssn'] = {'type': 'string'}
        return schema

    @classmethod
    def _update_person_fields(cls):
        return super()._update_person_fields() + ['ssn']

    @classmethod
    def _party_convert(cls, data, options, parameters):
        pool = Pool()
        API = pool.get('api')
        Party = pool.get('party.party')

        super()._party_convert(data, options, parameters)

        if 'ssn' in data and data['ssn']:
            try:
                # SSN control api is completely broken
                test_party = Party(ssn=data['ssn'], gender=data['gender'],
                    birth_date=data['birth_date'])
                Party.check_ssn_format(data['ssn'])
                ssn_key = test_party.get_ssn('ssn_key')
                ssn_no_key = test_party.get_ssn('ssn_no_key')
                test_party.ssn_key = ssn_key
                test_party.ssn_no_key = ssn_no_key
                test_party.check_ssn_key()
            except UserError:
                API.add_input_error({
                        'type': 'invalid_ssn',
                        'data': {
                            'ssn': data['ssn'],
                            },
                        })


class APIProduct(metaclass=PoolMeta):
    __name__ = 'api.product'

    @classmethod
    def _update_covered_party_domains_from_item_desc(cls, item_desc, domains):
        super()._update_covered_party_domains_from_item_desc(item_desc, domains)
        if item_desc.kind == 'person' and item_desc.ssn_required:
            domains['subscription']['person_domain']['fields'].append(
                {'code': 'ssn', 'required': True})
