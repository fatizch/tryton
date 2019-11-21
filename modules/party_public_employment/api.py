# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.config import config


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
        schema['properties']['work_country'] = {'type': 'string'}
        schema['properties']['work_subdivision'] = {'type': 'string'}
        schema['required'] += ['administrative_situation']
        return schema

    @classmethod
    def _create_version(cls, data):
        version = super()._create_version(data)
        version.administrative_situation = data['administrative_situation']
        if data.get('increased_index'):
            version.increased_index = data.get('increased_index')
        pool = Pool()
        API = pool.get('api')

        def update_subdivision(code, country):
            subdivision = pool.get('country.subdivision').search([
                ('code', '=', code), ('country', '=', country)])
            if not subdivision:
                API.add_input_error({
                    'type': 'invalid_work_subdivision',
                    'data': {
                        'work_subdivision': data['work_subdivision'],
                        },
                    })
            version.work_subdivision = subdivision[0]

        if data.get('work_country'):
            code = data['work_country']
            country = API.instance_from_code(
                'country.country', code)
            version.work_country = country
            if data.get('work_subdivision'):
                update_subdivision(f'{code}-{data["work_subdivision"]}',
                    country)
        else:
            if data.get('work_subdivision'):
                code = config.get('options', 'default_country', default='FR')
                country = pool.get('country.country').search([
                    ('code', '=', code)])
                if country:
                    update_subdivision(f'{code}-{data["work_subdivision"]}',
                        country[0])
        return version

    @classmethod
    def _create_party_examples(cls):
        examples = super()._create_party_examples()
        examples[-1]['input']['parties'][0]['employments'][0].update(
            {'administrative_situation': 'active', 'increased_index': 100,
             'work_country': 'FR', 'work_subdivision': '03'})

        return examples
