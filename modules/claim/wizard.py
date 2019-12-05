# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.i18n import gettext
from trytond.model.exceptions import ValidationError
from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.coog_core import model, fields, utils
from trytond.wizard import Wizard, StateView, Button, StateTransition

from trytond.modules.party.exceptions import EraseError


__all__ = [
    'CloseClaim',
    'ClaimCloseReasonView',
    'BenefitToDeliver',
    'SelectBenefits',
    'DeliverBenefits',
    'BenefitSelectExtraDataView',
    'PropagateBenefitExtraData',
    'LossSelectExtraDataView',
    'PropagateLossExtraData',
    'PartyErase',
    'SetOriginService',
    'SetOriginServiceSelect',
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
                    if not benefit.several_delivered and benefit in deliver:
                        continue
                    description = '<div><b>%s</b></div>' % (
                        gettext('claim.msg_coverage_information'))
                    for data in option.current_version.\
                            extra_data_as_string.split('\n'):
                        description += '<div>%s</div>' % data
                    if benefit.description:
                        description += '<div><b>%s</b></div>' % (
                            gettext('claim.msg_benefit_information'))
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
        'claim.sub_status', 'Substatus', required=True,
        domain=[('status', 'in', ['closed', 'dropped'])])


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


class BenefitSelectExtraDataView(model.CoogView):
    'Select Extra Data'
    __name__ = 'benefit.select_extra_data_view'

    extra_data = fields.Dict('extra_data', 'Extra Data',
        domain=[('id', 'in', Eval('available_extra_datas'))],
        depends=['available_extra_datas'])
    benefit = fields.Many2One('benefit', 'Benefit', readonly=True)
    available_extra_datas = fields.Many2Many('extra_data', None, None,
        'Possible Extra Datas', states={'invisible': True})


class PropagateBenefitExtraData(Wizard):
    'Propagate Extra Data On Claim Services'
    __name__ = 'benefit.propagate_extra_data'

    start_state = 'select_extra_data'
    select_extra_data = StateView(
        'benefit.select_extra_data_view',
        'claim.service_select_extra_data_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Propagate', 'propagate_extra_data', 'tryton-go-next',
                default=True)])
    propagate_extra_data = StateTransition()

    def default_select_extra_data(self, fields):
        context = Transaction().context
        assert context.get('active_model') == 'benefit'
        benefit = Pool().get('benefit')(context.get('active_id'))
        return {
            'extra_data': {x.name: None for x in benefit.extra_data_def},
            'benefit': benefit.id,
            'available_extra_datas': [e.id for e in benefit.extra_data_def]
            }

    def transition_propagate_extra_data(self):
        Service = Pool().get('claim.service')
        affected_services = Service.search(
            [('benefit', '=', self.select_extra_data.benefit)])
        services_to_save = []
        for service in affected_services:
            if service.loss is None:
                continue
            for extra_data in service.extra_datas:
                for key, value in self.select_extra_data.extra_data.items():
                    if key not in list(extra_data.extra_data_values.keys()):
                        extra_data.extra_data_values.update({key: value})
                        extra_data.extra_data_values = \
                            extra_data.extra_data_values
            service.extra_datas = service.extra_datas
            services_to_save.append(service)
        if services_to_save:
            Service.save(services_to_save)
        return 'end'


class LossSelectExtraDataView(model.CoogView):
    'Select Extra Data'
    __name__ = 'loss.select_extra_data_view'

    extra_data = fields.Dict('extra_data', 'Extra Data',
        domain=[('id', 'in', Eval('available_extra_datas'))],
        depends=['available_extra_datas'])
    loss = fields.Many2One('benefit.loss.description', 'Loss', readonly=True)
    available_extra_datas = fields.Many2Many('extra_data', None, None,
        'Possible Extra Datas', states={'invisible': True})


class PropagateLossExtraData(Wizard):
    'Propagate Extra Data On Claim Losses'
    __name__ = 'loss.propagate_extra_data'

    start_state = 'select_extra_data'
    select_extra_data = StateView(
        'loss.select_extra_data_view',
        'claim.loss_select_extra_data_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Propagate', 'propagate_extra_data', 'tryton-go-next',
                default=True)])
    propagate_extra_data = StateTransition()

    def default_select_extra_data(self, fields):
        context = Transaction().context
        assert context.get('active_model') == 'benefit.loss.description'
        loss = Pool().get('benefit.loss.description')(
            context.get('active_id'))
        return {
            'extra_data': {x.name: None for x in loss.extra_data_def},
            'loss': loss.id,
            'available_extra_datas': [e.id for e in loss.extra_data_def]
            }

    def transition_propagate_extra_data(self):
        Loss = Pool().get('claim.loss')
        affected_losses = Loss.search(
            [('loss_desc', '=', self.select_extra_data.loss)])
        extra_data_to_propagate = self.select_extra_data.extra_data
        for loss in affected_losses:
            new_extra_data = {}
            for key, value in extra_data_to_propagate.items():
                if key not in list(loss.extra_data.keys()):
                    new_extra_data[key] = value
            if new_extra_data:
                loss.extra_data.update(new_extra_data)
                loss.extra_data = loss.extra_data
        if affected_losses:
            Loss.save(affected_losses)
        return 'end'


class PartyErase(metaclass=PoolMeta):
    __name__ = 'party.erase'

    def check_erase(self, party):
        super(PartyErase, self).check_erase(party)
        Claim = Pool().get('claim')
        open_claims = Claim.search([
                ('claimant', '=', party),
                ('status', 'in', ['open', 'reopened'])
                ])
        if open_claims:
            raise EraseError(gettext(
                    'claim.msg_party_has_open_claim',
                    party=party.rec_name,
                    claims=', '.join(
                        c.rec_name for c in open_claims)))

    def claims_to_erase(self, party_id):
        Claim = Pool().get('claim')
        return Claim.search([('claimant', '=', party_id)])

    def to_erase(self, party_id):
        to_erase = super(PartyErase, self).to_erase(party_id)
        pool = Pool()
        EventLog = pool.get('event.log')
        Claim = pool.get('claim')
        claims_to_erase = [c.id for c in self.claims_to_erase(party_id)]
        to_erase.extend([
                (EventLog, [('claim', 'in', claims_to_erase)], True,
                    ['description'],
                    [None]),
                (Claim, [('id', 'in', claims_to_erase)], True,
                    [],
                    [])])
        return to_erase


class SetOriginService(Wizard):
    'Set Origin Service'

    __name__ = 'claim.service.set_origin'

    start_state = 'select_origin'
    select_origin = StateView('claim.service.set_origin.select',
        'claim.select_origin_service_view_form', [
            Button('Cancel', 'end', 'tryton-exit'),
            Button('Select', 'select', 'tryton-next', default=True),
            ])
    select = StateTransition()

    def default_select_origin(self, name):
        active_model, active_id, active_ids = utils.extract_context()
        assert active_model == 'claim.service'
        if len(active_ids) > 1:
            raise ValidationError(gettext('claim.msg_only_one_service'))

        Service = Pool().get('claim.service')
        active = Service(active_id)

        possible_origins = Service.search(
            self._possible_origins_domain(active))
        if len(possible_origins) == 0:
            raise ValidationError('no_possible_origins')
        return {
            'service': active_id,
            'possible_origins': [x.id for x in possible_origins],
            'origin':
            possible_origins[0].id if len(possible_origins) == 1 else None,
            }

    def _possible_origins_domain(self, service):
        return [
            ('loss.claim.claimant', '=', service.loss.claim.claimant),
            ('loss.start_date', '<=', service.loss.start_date),
            ('loss.loss_desc.loss_kind', '=', service.loss.loss_desc.loss_kind),
            ]

    def transition_select(self):
        if not self.select_origin.origin:
            raise ValidationError(gettext('claim.msg_origin_required'))
        self.select_origin.service.set_origin_service(
            self.select_origin.origin)
        return 'end'


class SetOriginServiceSelect(model.CoogView):
    'Select Origin Service'

    __name__ = 'claim.service.set_origin.select'

    service = fields.Many2One('claim.service', 'Service', readonly=True)
    origin = fields.Many2One('claim.service', 'Origin',
        domain=[('id', 'in', Eval('possible_origins'))],
        depends=['possible_origins'])
    possible_origins = fields.Many2Many('claim.service', None, None,
        'Possible origins', readonly=True)
