# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core.api import OBJECT_ID_SCHEMA
from trytond.modules.coog_core import utils


__all__ = [
    'APIParty',
    'APIEndorsement',
    ]


class APIParty(metaclass=PoolMeta):
    __name__ = 'api.party'

    @classmethod
    def _find_sepa_mandate(cls, party, account, data, date=None):
        pool = Pool()
        API = pool.get('api')
        Mandate = pool.get('account.payment.sepa.mandate')

        domain = [
            ('party', '=', party.id),
            ('account_number.account', '=', account),
            ('state', '=', 'validated'),
            ['OR',
                ('start_date', '=', None),
                ('start_date', '<=', date or utils.today()),
                ],
            ]
        if 'id' in data:
            domain.append(('id', '=', data['id']))
        else:
            domain.append(('identification', '=', data['number']))

        matches = Mandate.search(domain)

        if len(matches) == 1:
            return matches[0]

        # If there are multiple matches, the constraints on the mandate should
        # probably be updated so that it cannot happen
        assert len(matches) == 0

        API.add_input_error({
                'type': 'mandate_not_found',
                'data': {
                    'party': party.code,
                    'account_number': account.numbers[0].number_compact,
                    'mandate_%s' % domain[-1][0]: domain[-1][2],
                    },
                })


class APIEndorsement(metaclass=PoolMeta):
    __name__ = 'api.endorsement'

    @classmethod
    def _change_bank_account_update_party(cls, endorsement, parameters):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')

        super()._change_bank_account_update_party(endorsement, parameters)

        new_mandates = []
        for change in parameters.get('direct_debit_changes', []):
            if 'mandates' not in change:
                continue
            for mandate_data in change['mandates']:
                old_mandate = mandate_data['mandate']
                new_mandate = cls._change_bank_account_new_mandate(
                    old_mandate, change['new_account']['account'].numbers[0],
                    parameters['date'])
                mandate_data['new_mandate'] = new_mandate
                new_mandates.append(new_mandate)

        if new_mandates:
            Mandate.save(new_mandates)

    @classmethod
    def _change_bank_account_new_mandate(cls, previous_mandate, account,
            date):
        pool = Pool()
        Mandate = pool.get('account.payment.sepa.mandate')

        new_mandate = Mandate()
        new_mandate.party = previous_mandate.party
        new_mandate.account_number = account
        new_mandate.company = previous_mandate.company
        new_mandate.type = 'recurrent'
        new_mandate.scheme = 'CORE'
        new_mandate.state = 'validated'  # Are we sure?
        new_mandate.identification = previous_mandate.identification
        new_mandate.signature_date = previous_mandate.signature_date
        new_mandate.amendment_of = previous_mandate

        # No checks on date vs account start, should be enforced in convert /
        # validates
        new_mandate.start_date = date

        return new_mandate

    @classmethod
    def _change_bank_account_must_update_contract(cls, billing_info,
            contract, parameters):
        match = super()._change_bank_account_must_update_contract(billing_info,
            contract, parameters)
        if match is not None:
            for mandate in match.get('mandates', []):
                if mandate['mandate'] == billing_info.sepa_mandate:
                    return match
        return None

    @classmethod
    def _change_bank_account_update_contract(cls, billing_information,
            contract, match, parameters):
        previous_mandate = billing_information.sepa_mandate

        modified = super()._change_bank_account_update_contract(
            billing_information, contract, match, parameters)

        for mandate in match.get('mandates', []):
            if mandate['mandate'] == previous_mandate:
                modified.sepa_mandate = mandate['new_mandate']
                break
        return modified

    @classmethod
    def _change_bank_account_direct_debit_change_schema(cls):
        schema = super()._change_bank_account_direct_debit_change_schema()
        schema['items']['properties']['mandates'] = {
            'type': 'array',
            'additionalItems': False,
            'items': cls._change_bank_account_sepa_mandate_schema(),
            }
        schema['items']['required'].append('mandates')
        return schema

    @classmethod
    def _change_bank_account_sepa_mandate_schema(cls):
        return {
            'type': 'object',
            'additionalProperties': False,
            'properties': {
                'number': {'type': 'string'},
                'id': OBJECT_ID_SCHEMA,
                },
            'oneOf': [
                {
                    'required': ['number'],
                    },
                {
                    'required': ['id'],
                    },
                ],
            }

    @classmethod
    def _change_bank_account_direct_debit_convert_input(cls, changes,
            parameters):

        super()._change_bank_account_direct_debit_convert_input(changes,
            parameters)

        pool = Pool()
        API = pool.get('api')
        PartyAPI = pool.get('api.party')

        for mandate_data in changes['mandates']:
            mandate_data['mandate'] = PartyAPI._find_sepa_mandate(
                parameters['party'], changes['previous_account']['account'],
                mandate_data)
            if mandate_data['mandate'].amended_by:
                API.add_input_error({
                        'type': 'already_amended_mandate',
                        'data': {
                            'party': parameters['party'].code,
                            'mandate': mandate_data['mandate'].identification
                            },
                        })

    @classmethod
    def _change_bank_account_examples(cls):
        examples = super()._change_bank_account_examples()
        for example in examples:
            for change in example['input']['direct_debit_changes']:
                change['mandates'] = [
                    {
                        'number': 'RUM7182387123',
                        },
                    {
                        'id': 471273124,
                        },
                    ]
        return examples
