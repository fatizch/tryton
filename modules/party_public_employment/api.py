# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'APIParty',
]


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _party_employment_schema(cls):
        schema = super()._party_employment_schema()
        schema['properties']['administrative_situation'] = {
            'type': 'string',
            'enum': [x[0] for x in Pool().get(
                'party.employment.version').administrative_situation.selection],
            }
        schema['properties']['increased_index'] = {'type': 'integer'}
        schema['required'] += ['administrative_situation']
        return schema

    @classmethod
    def _create_version(cls, data):
        version = super()._create_version(data)
        version.administrative_situation = data['administrative_situation']
        if data.get('increased_index'):
            version.increased_index = data.get('increased_index')
        return version

    @classmethod
    def _create_party_examples(cls):
        examples = super()._create_party_examples()
        examples[-1]['input']['parties'][0]['employments'][0].update(
            {'administrative_situation': 'active', 'increased_index': 100})

        return examples
