# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from textwrap import TextWrapper

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.modules.coog_core import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'ClaimIndemnification',
    'ClaimService',
    'Claim',
    'ExtraData',
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
            ], 'Eligibility Status')
    eligibility_status_string = eligibility_status.translated(
        'eligibility_status')
    eligibility_comment = fields.Char('Eligibility Comment')
    eligibility_comment_wrapped = fields.Function(
        fields.Text('Eligibility Comment'),
        'on_change_with_eligibility_comment_wrapped')
    eligibility_extra_data_values = fields.Dict('extra_data',
        'Eligibility Extra Data')
    extra_eligibility_data_summary = fields.Function(
        fields.Text('Eligibility Extra Data Summary',
            depends=['eligibility_extra_data_values']),
        'get_eligibility_extra_data_summary')
    rejection_extra_data_values = fields.Dict('extra_data',
        'Rejection Extra Data')

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

    @staticmethod
    def default_eligibility_status():
        return 'study_in_progress'

    @classmethod
    def get_eligibility_extra_data_summary(cls, services, name):
        return Pool().get('extra_data').get_extra_data_summary(services,
            'eligibility_extra_data_values')

    def init_from_loss(self, loss, benefit):
        self.eligibility_extra_data_values = {}
        self.rejection_extra_data_values = {}
        super(ClaimService, self).init_from_loss(loss, benefit)

    @classmethod
    def get_wrapper(cls):
        return TextWrapper(width=79)

    @fields.depends('eligibility_comment', 'eligibility_status')
    def on_change_with_eligibility_comment_wrapped(self, name=None):
        comment = ''
        if (self.eligibility_status == 'accepted' and
                self.extra_eligibility_data_summary):
            comment = '%s\n' % self.extra_eligibility_data_summary
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
            if eligible:
                service.eligibility_status = 'accepted'
                accepted.append(service)
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

    def init_eligibility_extra_data_values(self):
        ExtraData = Pool().get('extra_data')
        extra_datas = ExtraData.search(
            [('kind', '=', 'manual_eligibility_reason')])
        self.eligibility_extra_data_values = {
            x.name: None for x in extra_datas}

    def init_rejection_extra_data_values(self):
        ExtraData = Pool().get('extra_data')
        extra_datas = ExtraData.search(
            [('kind', '=', 'manual_rejection_reason')])
        self.rejection_extra_data_values = {
            x.name: None for x in extra_datas}

    def get_all_extra_data(self, at_date):
        res = super(ClaimService, self).get_all_extra_data(at_date)
        res.update(self.eligibility_extra_data_values)
        return res

    def accept_eligibility(self, extra_data):
        self.__class__.write([self], {
                'eligibility_status': 'accepted',
                'eligibility_extra_data_values': extra_data})

    def reject_eligibility(self, extra_data):
        self.__class__.write([self], {
                'eligibility_status': 'refused',
                'rejection_extra_data_values': extra_data,
                })
        Pool().get('event').notify_events([self], 'refuse_claim_service')


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
