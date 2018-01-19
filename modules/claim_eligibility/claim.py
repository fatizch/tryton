# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from textwrap import TextWrapper

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.modules.coog_core import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    'ClaimService',
    'ExtraData',
    'ClaimIndemnification',
    ]


class Claim:
    __name__ = 'claim'

    all_services_refused = fields.Function(
        fields.Boolean('All services are refused'),
        'get_all_services_refused')

    def check_eligibility(self):
        Service = Pool().get('claim.service')
        Service.check_eligibility(self.delivered_services)

    def get_all_services_refused(self, name=None):
        return all(x.eligibility_status == 'refused'
            for x in self.delivered_services)


class ClaimService:
    __name__ = 'claim.service'

    eligibility_status = fields.Selection([
            ('study_in_progress', 'Study In Progress'),
            ('accepted', 'Accepted'),
            ('refused', 'Refused'),
            ], 'Eligibility Status', readonly=True)
    eligibility_status_string = eligibility_status.translated(
        'eligibility_status')
    eligibility_comment = fields.Char('Eligibility Comment')
    eligibility_comment_wrapped = fields.Function(
        fields.Text('Eligibility Comment'),
        'on_change_with_eligibility_comment_wrapped')
    eligibility_decision = fields.Many2One(
        'benefit.eligibility.decision', 'Eligibility Decision',
        ondelete='RESTRICT', select=True, domain=[
            ('id', 'in', Eval('possible_decisions')),
            ('state', '=', Eval('eligibility_status'))
            ],
        readonly=True, depends=['possible_decisions', 'eligibility_status'])
    possible_decisions = fields.Function(
        fields.Many2Many('benefit.eligibility.decision', None, None,
            'Possible Decisions'),
        getter='on_change_with_possible_decisions')

    @classmethod
    def __setup__(cls):
        super(ClaimService, cls).__setup__()
        cls._buttons.update({
            'validate_services': {},
            'check_eligibility': {
                'invisible': Eval('eligibility_status') != 'study_in_progress',
                },
            'reject_services': {},
            })
        cls._error_messages.update({
                'warning_refuse_service': 'Confirm service refusal'
                })

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        if benefit:
            self.eligibility_decision = benefit.decision_default
            if self.eligibility_decision:
                self.eligibility_status = \
                    self.eligibility_decision.state
            else:
                self.eligibility_status = 'study_in_progress'

    @fields.depends('benefit', 'eligibility_status')
    def on_change_with_possible_decisions(self, name=None):
        if self.benefit:
            return [x.id for x in self.benefit.eligibility_decisions]

    @classmethod
    def get_wrapper(cls):
        return TextWrapper(width=79)

    @fields.depends('eligibility_comment', 'eligibility_status')
    def on_change_with_eligibility_comment_wrapped(self, name=None):
        comment = ''
        if (self.eligibility_status == 'accepted' and
                self.eligibility_decision):
            comment = '%s\n' % self.eligibility_decision.description
        if (self.eligibility_status == 'refused' and
                self.eligibility_decision):
            comment = '%s\n' % self.eligibility_decision.description
        if not self.eligibility_comment:
            return comment
        wrapper = self.get_wrapper()
        return comment + '\n'.join(map(wrapper.fill,
                self.eligibility_comment.splitlines()))

    def calculate_eligibility(self):
        exec_context = {}
        self.init_dict_for_rule_engine(exec_context)
        exec_context['date'] = self.loss.start_date
        return self.benefit.check_eligibility(exec_context)

    @classmethod
    @model.CoogView.button
    def check_eligibility(cls, services):
        to_save = []
        accepted = []
        Event = Pool().get('event')
        for service in services:
            if service.eligibility_status != 'study_in_progress':
                continue
            eligible, message = service.calculate_eligibility()
            service.eligibility_comment = message
            if eligible and service.benefit.accept_decision_default:
                service.eligibility_decision = \
                    service.benefit.accept_decision_default
                service.eligibility_status = service.eligibility_decision.state
                accepted.append(service)
            elif not eligible and service.benefit.refuse_from_rules and \
                    service.benefit.refuse_decision_default:
                service.eligibility_decision = \
                    service.benefit.refuse_decision_default
                service.eligibility_status = service.eligibility_decision.state
            to_save.append(service)
        if to_save:
            cls.save(to_save)
        if accepted:
            Event.notify_events(accepted, 'accept_claim_service')

    @classmethod
    @model.CoogView.button_action(
        'claim_eligibility.act_validate_eligibility_wizard')
    def validate_services(cls, services):
        pass

    @classmethod
    @model.CoogView.button_action(
        'claim_eligibility.act_reject_eligibility_wizard')
    def reject_services(cls, services):
        pass

    def accept_eligibility(self, decision):
        self.__class__.write([self], {
                'eligibility_status': decision.state,
                'eligibility_decision': decision.id})

    def reject_eligibility(self, decision):
        self.__class__.write([self], {
                'eligibility_status': decision.state,
                'eligibility_decision': decision.id,
                })
        Pool().get('event').notify_events([self], 'refuse_claim_service')

    def getter_can_be_indemnified(self, name):
        return super(ClaimService, self).getter_can_be_indemnified(name) \
            and self.eligibility_status != 'refused'

    @classmethod
    def searcher_can_be_indemnified(cls, name, clause):
        return ['AND',
            super(ClaimService, cls).searcher_can_be_indemnified(
                name, clause),
            [('eligibility_status', '!=', 'refused')]
            ]


class ClaimIndemnification:
    __metaclass__ = PoolMeta
    __name__ = 'claim.indemnification'

    @classmethod
    def __setup__(cls):
        super(ClaimIndemnification, cls).__setup__()
        cls._error_messages.update({
                'ineligible': 'The claim service is not eligible',
                })

    @classmethod
    def check_schedulability(cls, indemnifications):
        super(ClaimIndemnification, cls).check_schedulability(indemnifications)
        for i in indemnifications:
            if i.service.eligibility_status != 'accepted':
                cls.append_functional_error('ineligible')


class ExtraData:
    __name__ = 'extra_data'

    @classmethod
    def __setup__(cls):
        super(ExtraData, cls).__setup__()
        cls.kind.selection.append(('manual_eligibility_reason',
                'Claim: Manual Eligibility Reason'))
        cls.kind.selection.append(('manual_rejection_reason',
                'Claim: Manual Rejection Reason'))
