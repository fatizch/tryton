from textwrap import TextWrapper

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields

__metaclass__ = PoolMeta
__all__ = [
    'ClaimService',
    'Claim'
    ]


class Claim:
    __name__ = 'claim'

    def check_eligibility(self):
        Service = Pool().get('claim.service')
        Service.check_eligibility(self.delivered_services)


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

    @classmethod
    def __setup__(cls):
        super(ClaimService, cls).__setup__()
        cls._buttons.update({
            'accept_services': {
                'invisible': Eval('eligibility_status') != 'study_in_progress',
                },
            'refuse_services': {
                'invisible': Eval('eligibility_status') != 'study_in_progress',
                },
            'check_eligibility': {
                'invisible': Eval('eligibility_status') != 'study_in_progress',
                }
            })

    @staticmethod
    def default_eligibility_status():
        return 'study_in_progress'

    @classmethod
    def get_wrapper(cls):
        return TextWrapper(width=79)

    @fields.depends('eligibility_comment')
    def on_change_with_eligibility_comment_wrapped(self, name=None):
        if not self.eligibility_comment:
            return ''
        wrapper = self.get_wrapper()
        return '\n'.join(map(wrapper.fill,
                self.eligibility_comment.splitlines()))

    def calculate_eligibility(self):
        exec_context = {}
        self.init_dict_for_rule_engine(exec_context)
        exec_context['date'] = self.loss.start_date
        return self.benefit.check_eligibility(exec_context)

    @classmethod
    @model.CoopView.button
    def check_eligibility(cls, services):
        to_accept = []
        to_save = []
        for service in services:
            if service.eligibility_status != 'study_in_progress':
                continue
            eligible, message = service.calculate_eligibility()
            if eligible:
                to_accept.append(service)
            else:
                service.eligibility_comment = message
                to_save.append(service)
        cls.save(to_save)
        cls.accept_services(to_accept)

    @classmethod
    @model.CoopView.button
    def accept_services(cls, services):
        pool = Pool()
        Event = pool.get('event')
        cls.write(services, {
                'eligibility_status': 'accepted',
                'eligibility_comment': '',
                })
        Event.notify_events(services, 'accept_claim_service')

    @classmethod
    @model.CoopView.button
    def refuse_services(cls, services):
        pool = Pool()
        Event = pool.get('event')
        cls.write(services, {
                'eligibility_status': 'refused',
                })
        Event.notify_events(services, 'refuse_claim_service')
