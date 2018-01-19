# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.coog_core import model, fields


__all__ = [
    'ClaimServiceManualDisplay',
    'ManualValidationEligibility',
    'ManualRejectionEligibility',
    ]


class ClaimServiceManualDisplay(model.CoogView):
    'Claim Service Manual Display'
    __name__ = 'claim.service.manual'

    eligibility_decision = fields.Many2One(
        'benefit.eligibility.decision', 'Eligibility Decision',
        domain=[('id', 'in', Eval('possible_decisions'))],
        depends=['possible_decisions'])
    possible_decisions = fields.One2Many('benefit.eligibility.decision', None,
        'Possible Decisions')


class ManualValidationEligibility(Wizard):
    'Manual Validation Eligibility'
    __name__ = 'claim.manual_validation_eligibility'

    start_state = 'check_possibilities'
    check_possibilities = StateTransition()
    display_service = StateView('claim.service.manual',
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
                'validation_needs_decision':
                'Validation cannot be processed without knowing the reason',
                'eligibility_data_change': 'Eligibility information change. '
                'It could be necessary to recalculate existing indemnification'
                ' period.'})

    def transition_check_possibilities(self):
        pool = Pool()
        Service = pool.get('claim.service')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return 'end'
        assert Transaction().context.get('active_model') == 'claim.service'
        service = Service(active_id)
        possible_eligibilities = [x for x in service.possible_decisions
            if x.state == 'accepted']
        if possible_eligibilities:
            self.display_service.possible_decisions = \
                possible_eligibilities
            return 'display_service'
        return 'finalize_validation'

    def default_display_service(self, fields):
        return {
            'possible_decisions': [x.id for x in
                self.display_service.possible_decisions],
            }

    def transition_check_result(self):
        if not self.display_service.eligibility_decision:
            self.raise_user_error('validation_needs_decision')
        return 'finalize_validation'

    def transition_finalize_validation(self):
        pool = Pool()
        Event = pool.get('event')
        Service = pool.get('claim.service')
        active_id = Transaction().context.get('active_id')
        service = Service(active_id)
        if (service.eligibility_status == 'accepted' and
                service.eligibility_decision !=
                self.display_service.eligibility_decision):
            self.raise_user_warning('eligibility_data_change',
                'eligibility_data_change')
        Service.accept_eligibility(service,
            self.display_service.eligibility_decision)
        Event.notify_events([service], 'accept_claim_service')
        return 'end'


class ManualRejectionEligibility(Wizard):
    'Manual Rejection Eligibility'
    __name__ = 'claim.manual_rejection_eligibility'

    start_state = 'check_possibilities'
    check_possibilities = StateTransition()
    select_reason = StateView('claim.service.manual',
        'claim_eligibility.reject_eligibility_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Validate', 'check_selection', 'tryton-go-next',
                default=True)])
    check_selection = StateTransition()
    register_reason = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ManualRejectionEligibility, cls).__setup__()
        cls._error_messages.update({
                'rejection_needs_decision':
                'Rejection cannot be processed without knowing the reason',
                'eligibility_change': 'Eligibility information changed. It '
                'may be necessary to recompute existing indemnification '
                'periods.'})

    def transition_check_possibilities(self):
        pool = Pool()
        Service = pool.get('claim.service')
        active_id = Transaction().context.get('active_id')
        if not active_id:
            return 'end'
        assert Transaction().context.get('active_model') == 'claim.service'
        service = Service(active_id)
        possible_eligibilities = [x for x in service.possible_decisions
            if x.state == 'refused']
        if possible_eligibilities:
            self.select_reason.possible_decisions = \
                possible_eligibilities
            return 'select_reason'
        return 'end'

    def default_select_reason(self, fields):
        return {
            'possible_decisions': [x.id for x in
                self.select_reason.possible_decisions]
            }

    def transition_check_selection(self):
        if not self.select_reason.eligibility_decision:
                self.raise_user_error('rejection_needs_decision')
        return 'register_reason'

    def transition_register_reason(self):
        Service = Pool().get('claim.service')
        active_id = Transaction().context.get('active_id')
        service = Service(active_id)
        if (service.eligibility_status == 'refused' and
                service.eligibility_decision !=
                self.select_reason.eligibility_decision):
            self.raise_user_warning('eligibility_change', 'eligibility_change')
        Service.reject_eligibility(service,
            self.select_reason.eligibility_decision)
        return 'end'
