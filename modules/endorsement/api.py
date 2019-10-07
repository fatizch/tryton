# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.api import APIMixin, DATE_SCHEMA, date_from_api
from trytond.modules.coog_core import utils
from trytond.modules.coog_core.api import CODED_OBJECT_SCHEMA


__all__ = [
    'APIConfiguration',
    'APIEndorsement',
    ]


class APIConfiguration(metaclass=PoolMeta):
    __name__ = 'api.configuration'


class APIEndorsement(APIMixin):
    'Endorsement APIs'

    __name__ = 'api.endorsement'

    @classmethod
    def get_api_endorsement_definition(cls, api_name, definition_data):
        pool = Pool()
        API = pool.get('api')
        Definition = pool.get('endorsement.definition')
        APIConfiguration = pool.get('api.configuration')

        target_field = APIConfiguration._fields['%s_definition' % api_name]
        if definition_data is None:
            definition = getattr(APIConfiguration(1),
                '%s_definition' % api_name)
            if not definition:
                API.add_input_error({
                        'type': 'missing_endorsement_configuration',
                        'data': {
                            'api_name': api_name,
                            },
                        })
        else:
            definition = API.instantiate_code_object('endorsement.definition',
                definition_data)

            # Check constraints
            if not Definition.search(
                    [target_field.domain, [('id', '=', definition.id)]]):
                API.add_input_error({
                        'type': 'invalid_endorsement_code',
                        'data': {
                            'api_name': api_name,
                            'code': definition.code,
                            },
                        })

        return definition

    @classmethod
    def _complete_endorsement(cls, endorsement, options):
        Endorsement = Pool().get('endorsement')

        endorsement.save()
        Endorsement.apply([endorsement])

        result = {
            'endorsements': [
                cls._complete_endorsement_result(endorsement),
                ],
            }

        if not options.get('auto_apply_generated', False):
            return result

        generated_ids = [x.id for x in Endorsement.search([
                    ('generated_by', '=', endorsement.id)])]

        # We commit the transaction since other endorsements may fail,
        # but we want to go the farthest we can. We could actually to this only
        # if there are generated endorsements, but that would mean an
        # unpredictable behaviour for the api
        Transaction().commit()

        for generated_endorsement in generated_ids:
            with Transaction().new_transaction() as transaction:
                try:
                    Endorsement.apply(
                        [Endorsement(generated_endorsement)])
                    transaction.commit()
                except Exception:
                    transaction.rollback()

        # We must open a new transaction in order to have access to the latest
        # informations
        with Transaction().new_transaction() as transaction:
            result['endorsements'] += [
                cls._complete_endorsement_result(x)
                for x in Endorsement.browse(generated_ids)]
        return result

    @classmethod
    def _complete_endorsement_result(cls, endorsement):
        return {
            'id': endorsement.id,
            'number': endorsement.number,
            'state': endorsement.state,
            'definition': endorsement.definition.code,
            }

    @classmethod
    def _endorsement_base_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'date': DATE_SCHEMA,
                'endorsement_definition': CODED_OBJECT_SCHEMA,
                'options': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'auto_apply_generated': {'type': 'boolean'},
                        },
                    },
                },
            }

    @classmethod
    def _endorsement_base_output_schema(cls):
        Endorsement = Pool().get('endorsement')

        return {
            'type': 'object',
            'additionalProperties': False,
            'required': ['endorsements'],
            'properties': {
                'endorsements': {
                    'type': 'array',
                    'additionalItems': False,
                    'items': {
                        'type': 'object',
                        'additionalProperties': False,
                        'required': ['id', 'number', 'state', 'definition'],
                        'properties': {
                            'id': {'type': 'integer'},
                            'number': {'type': 'string'},
                            'state': {
                                'type': 'string',
                                'enum': [
                                    x[0] for x in Endorsement.state.selection],
                                },
                            'definition': {'type': 'string'},
                            },
                        },
                    },
                },
            }

    @classmethod
    def _endorsement_base_convert_input(cls, api_name, parameters):
        pool = Pool()
        API = pool.get('api')

        parameters['endorsement_definition'] = \
            cls.get_api_endorsement_definition(api_name,
                parameters.get('endorsement_definition', None))

        if 'date' in parameters:
            parameters['date'] = date_from_api(parameters['date'])
        else:
            parameters['date'] = utils.today()

        if 'options' in parameters and parameters['options'].get(
                'auto_apply_generated', False):
            if not parameters['endorsement_definition'].next_endorsement:
                API.add_input_error({
                        'type': 'no_generated_definition',
                        'data': {
                            'definition':
                            parameters['endorsement_definition'].code,
                            },
                        })
        return parameters
