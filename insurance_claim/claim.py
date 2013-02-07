#-*- coding:utf-8 -*-
import copy
from trytond.model import fields
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import model, utils
from trytond.modules.insurance_product.benefit import INDEMNIFICATION_KIND
__all__ = [
    'Claim',
    'Loss',
    'ClaimDeliveredService',
    'Indemnification',
    'IndemnificationDetail',
]

CLAIM_STATUS = [
    ('in_progress', 'In Progress'),
    ('waiting_client', 'Waiting from Client'),
    ('closed', 'Closed'),
    ('litigation', 'litigation'),
]

CLAIM_CLOSED_REASON = [
    ('refusal', 'Refusal'),
    ('paid', 'Paid'),
]


INDEMNIFICATION_STATUS = [
    ('calculated', 'Calculated'),
    ('validated', 'Validated'),
    ('refused', 'Refused'),
    ('paid', 'Paid'),
]

INDEMNIFICATION_DETAIL_KIND = [
    ('waiting_period', 'Waiting Period'),
    ('deductible', 'Deductible'),
    ('limit', 'Limit'),
    ('included', 'Included'),
]


class Claim(model.CoopSQL, model.CoopView):
    'Claim'

    __name__ = 'ins_claim.claim'

    name = fields.Char('Number', select=True)
    status = fields.Selection(CLAIM_STATUS, 'Status', sort=False)
    sub_status = fields.Selection('get_possible_sub_status', 'Sub Status',
        selection_change_with=['status'])
    declaration_date = fields.Date('Declaration Date')
    end_date = fields.Date('End Date',
        states={'invisible': Eval('status') != 'closed'})
    closed_reason = fields.Function(
        fields.Selection(CLAIM_CLOSED_REASON, 'Closed Reason',
            states={'invisible': Eval('status') != 'closed'}),
        'get_closed_reason')
    claimant = fields.Many2One('party.party', 'Claimant')
    losses = fields.One2Many('ins_claim.loss', 'claim', 'Losses')

    def get_possible_sub_status(self):
        if self.status == 'closed':
            return CLAIM_CLOSED_REASON
        return [('', '')]

    def get_closed_reason(self, name):
        if self.status == 'closed':
            return self.sub_status
        return [('', '')]

    @staticmethod
    def default_declaration_date():
        return utils.today()

    @staticmethod
    def default_status():
        return 'in_progress'


class Loss(model.CoopSQL, model.CoopView):
    'Loss'

    __name__ = 'ins_claim.loss'

    claim = fields.Many2One('ins_claim.claim', 'Claim', ondelete='CASCADE')
    start_date = fields.Date('Loss Date')
    end_date = fields.Date('End Date',
        states={'invisible': Bool(~Eval('with_end_date'))},
        depends=['with_end_date'])
    loss_desc = fields.Many2One('ins_product.loss_desc', 'Loss Descriptor',
        ondelete='RESTRICT')
    event_desc = fields.Many2One('ins_product.event_desc', 'Event',
        domain=[
            ('loss_descs', '=', Eval('loss_desc'))
        ],
        depends=['loss_desc'], ondelete='RESTRICT')
    delivered_services = fields.One2Many('ins_contract.delivered_service',
        'loss', 'Delivered Services')
    main_loss = fields.Many2One('ins_claim.loss', 'Main Loss',
        ondelete='CASCADE')
    sub_losses = fields.One2Many('ins_claim.loss', 'main_loss', 'Sub Losses')
    with_end_date = fields.Function(
        fields.Boolean('With End Date', on_change_with=['loss_desc']),
        'on_change_with_with_end_date')
    complementary_data = fields.Dict(
        'Complementary Data',
        schema_model='ins_product.complementary_data_def',
        on_change_with=['loss_desc', 'complementary_data'])

    def on_change_with_with_end_date(self, name):
        res = False
        if self.loss_desc:
            res = self.loss_desc.with_end_date
        return res

    def on_change_with_complementary_data(self):
        res = {}
        if self.loss_desc:
            res = utils.init_complementary_data(
                self.loss_desc.complementary_data_def)
        return res


class ClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    loss = fields.Many2One('ins_claim.loss', 'Loss', ondelete='CASCADE')
    benefit = fields.Many2One('ins_product.benefit', 'Benefit',
        ondelete='RESTRICT',
        domain=[
            ('loss_descs', '=', Eval('_parent_loss', {}).get('loss_desc'))
        ])
    indemnifications = fields.One2Many('ins_claim.indemnification',
        'delivered_service', 'Indemnifications')

    @classmethod
    def __setup__(cls):
        super(ClaimDeliveredService, cls).__setup__()
        cls.subscribed_service = copy.copy(cls.subscribed_service)
        if not cls.subscribed_service.domain:
            cls.subscribed_service.domain = []
        domain = ('offered.benefits.loss_descs', '=',
            Eval('_parent_loss', {}).get('loss_desc'))
        cls.subscribed_service.domain.append(domain)


class Indemnification(model.CoopSQL, model.CoopView):
    'Indemnification'

    __name__ = 'ins_claim.indemnification'

    delivered_service = fields.Many2One('ins_contract.delivered_service',
        'Delivered Service', ondelete='CASCADE')
    kind = fields.Selection(INDEMNIFICATION_KIND, 'Kind', sort=False)
    start_date = fields.Date('Start Date',
        states={'invisible': Eval('kind') != 'period'})
    end_date = fields.Date('End Date',
        states={'invisible': Eval('kind') != 'period'})
    status = fields.Selection(INDEMNIFICATION_STATUS, 'Status', sort=False)
    amount = fields.Numeric('Amount')
    details = fields.One2Many('ins_claim.indemnification_detail',
        'indemnification', 'Details')


class IndemnificationDetail(model.CoopSQL, model.CoopView):
    'Indemnification Detail'

    __name__ = 'ins_claim.indemnification_detail'

    indemnification = fields.Many2One('ins_claim.indemnification',
        'Indemnification', ondelete='CASCADE')
    start_date = fields.Date('Start Date',
        states={
            'invisible': Eval('_parent_indemnification', {}).get('kind') !=
                'period'})
    end_date = fields.Date('End Date',
       states={
            'invisible': Eval('_parent_indemnification', {}).get('kind') !=
                'period'})
    kind = fields.Selection(INDEMNIFICATION_DETAIL_KIND, 'Kind', sort=False)
    amount_per_period = fields.Numeric('Amount per Period')
