# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import base64

from trytond.pool import PoolMeta
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA
from trytond.pool import Pool
from trytond.modules.api import APIInputError

__all__ = ['APICore']


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._apis.update({
                'load_web_resources': {
                    'public': True,
                    'readonly': True,
                    'description': 'Retrieve Informations On Web Resources',
                    },
                }
            )

    @classmethod
    def load_web_resources(cls, parameters):
        response = []
        for param in parameters:
            response_item = dict(param)
            resource = response_item.pop('resource')
            tech_kind = resource.technical_kind
            response_item['technical_kind'] = tech_kind
            if tech_kind == 'binary':
                response_item['binary_value'] = base64.b64encode(
                    resource.binary_value).decode()
                response_item['filename'] = resource.filename
            elif tech_kind == 'text':
                response_item['value'] = resource.value
            else:
                raise NotImplementedError
            response.append(response_item)
        return response

    @classmethod
    def _load_web_resources_schema(cls):
        return {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'key': {'type': 'string'},
                    'model': {'type': 'string'},
                    'identifier': CODED_OBJECT_SCHEMA,
                    },
                }
            }

    @classmethod
    def _load_web_resources_output_schema(cls):
        return {
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'properties': {
                    'key': {'type': 'string'},
                    'model': {'type': 'string'},
                    'identifier': CODED_OBJECT_SCHEMA,
                    'technical_kind': {'type': 'string'},
                    'value': {'type': 'string'},
                    'binary_value': {'type': 'string'},
                    'filename': {'type': 'string'}
                    },
                }
            }

    @classmethod
    def _load_web_resources_examples(cls):
        return [
            {
                'input': [
                    {
                        'model': 'res.user',
                        'identifier': {'code': 'some_code'},
                        'key': 'some_key',
                        }
                    ],
                'output': [
                    {
                        'key': 'some_key',
                        'technical_kind': 'text',
                        'model': 'res.user',
                        'identifier': {'code': 'some_code'},
                        'value': 'some_value'
                        }
                    ],
                },
            {
                'input': [
                    {
                        'model': 'res.user',
                        'identifier': {'code': 'some_code'},
                        'key': 'some_key_for_binary',
                        }
                    ],
                'output': [
                    {
                        'key': 'some_key_for_binary',
                        'technical_kind': 'binary',
                        'model': 'res.user',
                        'identifier': {'code': 'some_code'},
                        'binary_value': 'Ym9uam91cgo=',
                        }
                    ],
                }
            ]

    @classmethod
    def _load_web_resources_convert_input(cls, parameters):
        pool = Pool()
        API = pool.get('api')
        for param in parameters:
            try:
                pool.get(param['model'])
            except KeyError:
                raise APIInputError([{
                        'type': 'unknown_model',
                        'data': param,
                        }])
            identifier = API.instantiate_code_object(param['model'],
                param['identifier'])
            try:
                param['resource'] = identifier.get_web_resource_by_key(
                    param['key'], instance=True)
            except KeyError:
                raise APIInputError([{
                            'type': 'no_such_web_ui_resource',
                            'data': param,
                            }])
        return parameters
