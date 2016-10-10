# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields


__all__ = [
    'IndemnificationDefinition',
    'CreateIndemnification',
    ]


class IndemnificationDefinition:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification_definition'

    @fields.depends('beneficiary')
    def on_change_service(self):
        super(IndemnificationDefinition, self).on_change_service()

    @fields.depends('beneficiary', 'possible_products', 'product', 'service')
    def on_change_beneficiary(self):
        self.update_product()

    def get_possible_products(self, name):
        if not self.beneficiary or self.beneficiary.is_person:
            return super(IndemnificationDefinition,
                self).get_possible_products(name)
        if self.service:
            return [x.id for x in self.service.benefit.company_products]
        return []


class CreateIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.create_indemnification'

    @classmethod
    def __setup__(cls):
        super(CreateIndemnification, cls).__setup__()
        cls._error_messages.update({
                'bad_start_date': 'The contract was terminated on the '
                '%(contract_end)s, a new indemnification cannot start on '
                '%(indemn_start)s.',
                'truncated_end_date': 'The contract was terminated on the '
                '%(contract_end)s, so the requested indemnification end ('
                '%(indemn_end)s) will automatically be updated',
                'lock_end_date': 'The contract was terminated on the '
                '%(contract_end)s, there will not be any revaluation '
                'after this date',
                })

    def default_definition(self, name):
        defaults = super(CreateIndemnification, self).default_definition(name)
        if not defaults.get('service', None) or not defaults.get('start_date',
                None):
            return defaults
        service = Pool().get('claim.service')(defaults['service'])
        if service.contract and service.contract.end_date:
            contract_end = service.contract.end_date
            if contract_end < defaults['start_date']:
                if (service.contract.post_termination_claim_behaviour ==
                        'stop_indemnifications'):
                    self.raise_user_error('bad_start_date', {
                            'indemn_start': defaults['start_date'],
                            'contract_end': contract_end})
        return defaults

    def check_input(self):
        super(CreateIndemnification, self).check_input()
        input_start_date = self.definition.start_date
        input_end_date = self.definition.end_date
        service = self.definition.service
        if (input_start_date and service.contract and
                service.contract.end_date):
            contract_end = service.contract.end_date
            behaviour = service.contract.post_termination_claim_behaviour
            if contract_end < input_start_date:
                if behaviour == 'stop_indemnifications':
                    self.raise_user_error('bad_start_date', {
                            'indemn_start': input_start_date,
                            'contract_end': contract_end})
            if contract_end < input_end_date:
                if behaviour == 'stop_indemnifications':
                    self.raise_user_warning(
                        'truncated_end_date_%i' % service.id,
                        'truncated_end_date', {
                            'indemn_end': input_end_date,
                            'contract_end': contract_end})
                    input_end_date = contract_end
                elif behaviour == 'lock_indemnifications':
                    self.raise_user_warning(
                        'lock_end_date_%i' % service.id,
                        'lock_end_date', {
                            'indemn_end': input_end_date,
                            'contract_end': contract_end})
