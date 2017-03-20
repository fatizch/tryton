# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction


__all__ = [
    'ManualValidationEligibility',
    ]


class ManualValidationEligibility(Wizard):
    'Manual Validation Eligibility'
    __name__ = 'claim.manual_validation_eligibility'

    start_state = 'check_extra_data'
    check_extra_data = StateTransition()
    display_service = StateView('claim.service',
        'claim_eligibility.validate_eligibility_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'check_result', 'tryton-go-next',
                default=True)])
    check_result = StateTransition()
    finalize_validation = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManualValidationEligibility, cls).__setup__()
        cls._error_messages.update({
                'validation_eligibility_need_extra_data':
                'Validation cannot be processed without knowing the reason : '
                '%s must be filled',
                'eligibility_data_change': 'Eligibility information change. '
                'It could be necessary to recalculate existing indemnification'
                ' period.'})

    def transition_check_extra_data(self):
        pool = Pool()
        Service = pool.get('claim.service')
        assert Transaction().context.get('active_model') == 'claim.service'
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return 'end'
        service = Service(active_id)
        if not service.eligibility_extra_data_values:
            service.init_eligibility_extra_data_values()
        self.display_service.eligibility_extra_data_values = \
            service.eligibility_extra_data_values
        if service.eligibility_extra_data_values:
            return 'display_service'
        return 'finalize_validation'

    def default_display_service(self, fields):
        return {
            'eligibility_extra_data_values':
            self.display_service.eligibility_extra_data_values
            }

    def transition_check_result(self):
        extradata = self.display_service.eligibility_extra_data_values
        for key, value in extradata.iteritems():
            if value is None:
                self.raise_user_error('validation_eligibility_need_extra_data',
                    key)
        return 'finalize_validation'

    def transition_finalize_validation(self):
        pool = Pool()
        Event = pool.get('event')
        Service = pool.get('claim.service')
        active_id = Transaction().context.get('active_id')
        service = Service(active_id)
        if (service.eligibility_status == 'accepted' and
                service.eligibility_extra_data_values !=
                self.display_service.eligibility_extra_data_values):
            self.raise_user_warning('eligibility_data_change',
                'eligibility_data_change')
        Service.accept_eligibility(service,
            self.display_service.eligibility_extra_data_values)
        Event.notify_events([service], 'accept_claim_service')
        return 'end'
