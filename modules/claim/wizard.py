# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.transaction import Transaction
from trytond.modules.coog_core import model, fields
from trytond.wizard import Wizard, StateView, Button, StateTransition


__metaclass__ = PoolMeta
__all__ = [
    'CloseClaim',
    'ClaimCloseReasonView',
    'BenefitToDeliver',
    'SelectBenefits',
    'DeliverBenefits',
    ]


class BenefitToDeliver(model.CoogView):
    'Benefit To Deliver'

    __name__ = 'claim.benefit_to_deliver'

    to_deliver = fields.Boolean('To Deliver')
    benefit = fields.Many2One('benefit', 'Benefit', readonly=True)
    benefit_description = fields.Text('Description', readonly=True)
    contract = fields.Many2One('contract', 'Contract', readonly=True)
    covered_element = fields.Many2One('contract.covered_element',
        'Covered Element', readonly=True)
    option = fields.Many2One('contract.option', 'Option', readonly=True)
    loss = fields.Many2One('claim.loss', 'Loss', readonly=True)


class SelectBenefits(model.CoogView):
    'Select benefits'

    __name__ = 'claim.select_benefits'

    benefits_to_deliver = fields.One2Many('claim.benefit_to_deliver', None,
        'Benefits To Deliver')
    claim = fields.Many2One('claim', 'Claim')


class DeliverBenefits(Wizard):
    'Deliver benefit'
    __name__ = 'claim.deliver_benefits'

    start_state = 'benefits'
    benefits = StateView('claim.select_benefits',
        'claim.select_benefit_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Deliver', 'deliver', 'tryton-go-next')])
    deliver = StateTransition()

    @classmethod
    def __setup__(cls):
        super(DeliverBenefits, cls).__setup__()
        cls._error_messages.update({
                'coverage_information': 'Coverage Information',
                'benefit_information': 'Benefit Information',
                })

    def default_benefits(self, name):
        pool = Pool()
        Claim = pool.get('claim')
        claim_id = Transaction().context.get('active_id')
        claim = Claim(claim_id)

        benefits_to_deliver = []
        for loss in claim.losses:
            deliver = [service.benefit for service in loss.services]
            for contract in claim.possible_contracts:
                for benefit, option in contract.get_possible_benefits(loss):
                    if benefit in deliver:
                        continue
                    description = '<div><b>%s</b></div>' % \
                        self.raise_user_error('coverage_information',
                            raise_exception=False)
                    for data in option.current_version.\
                            extra_data_as_string.split('\n'):
                        description += '<div>%s</div>' % data
                    if benefit.description:
                        description += '<div><b>%s</b></div>' % \
                            self.raise_user_error('coverage_information',
                                raise_exception=False)
                        description += '<div>%s</div>' % benefit.description
                    benefits_to_deliver += [{
                            'to_deliver': True,
                            'benefit': benefit.id,
                            'benefit_description': description,
                            'contract': contract.id,
                            'covered_element': option.covered_element.id if
                            option.covered_element else None,
                            'option': option.id,
                            'loss': loss.id
                            }]
        res = {
            'claim': claim_id,
            'benefits_to_deliver': benefits_to_deliver,
            }
        return res

    def transition_deliver(self):
        pool = Pool()
        Services = pool.get('claim.service')
        to_save = []
        for to_deliver in self.benefits.benefits_to_deliver:
            if not to_deliver.to_deliver:
                continue
            to_deliver.loss.init_services(to_deliver.option,
                [to_deliver.benefit])
            to_save.extend(to_deliver.loss.services)
        Services.save(to_save)
        return 'end'


class ClaimCloseReasonView(model.CoogView):
    'Claim Close Reason View'

    __name__ = 'claim.close_reason_view'

    claims = fields.Many2Many('claim', '', '', 'Claims', readonly=True)
    sub_status = fields.Many2One(
        'claim.sub_status', 'Substatus', required=True)


class CloseClaim(Wizard):
    'Close Claims'
    __name__ = 'claim.close'

    start_state = 'close_reason'
    close_reason = StateView(
        'claim.close_reason_view',
        'claim.close_reason_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Apply', 'apply_sub_status', 'tryton-go-next',
                default=True)])
    apply_sub_status = StateTransition()

    def default_close_reason(self, fields):
        context = Transaction().context
        assert context.get('active_model') == 'claim'
        return {'claims': context.get('active_ids')}

    def transition_apply_sub_status(self):
        Claim = Pool().get('claim')
        Claim.close(self.close_reason.claims, self.close_reason.sub_status)
        return 'end'
