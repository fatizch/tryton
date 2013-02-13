#-*- coding:utf-8 -*-
import copy
from trytond.model import fields
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import model, utils, date
from trytond.modules.coop_process import CoopProcessFramework
from trytond.modules.insurance_product.benefit import INDEMNIFICATION_KIND, \
    INDEMNIFICATION_DETAIL_KIND

__all__ = [
    'Claim',
    'Loss',
    'ClaimDeliveredService',
    'Indemnification',
    'IndemnificationDetail',
    'DocumentRequest',
    'Document',
    'RequestFinder',
    'ContactHistory',
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


class Claim(model.CoopSQL, CoopProcessFramework):
    'Claim'

    __name__ = 'ins_claim.claim'

    name = fields.Char('Number', select=True,
        states={
            'readonly': True
        },)
    status = fields.Selection(CLAIM_STATUS, 'Status', sort=False,
        states={
            'readonly': True
        },)
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
    documents = fields.One2Many(
        'ins_product.document_request',
        'needed_by',
        'Documents',
    )

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

    def init_loss(self):
        if hasattr(self, 'losses') and self.losses:
            return True
        loss = utils.instanciate_relation(self.__class__, 'losses')
        loss.init_from_claim(self)
        self.losses = [loss]
        return True

    def get_main_contact(self):
        return self.claimant

    def set_claim_number(self):
        Generator = Pool().get('ir.sequence')
        good_gen, = Generator.search([
            ('code', '=', 'ins_claim.claim'),
        ], limit=1)
        self.name = good_gen.get_id(good_gen.id)
        return True


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

    def on_change_with_with_end_date(self, name=None):
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

    def init_from_claim(self, claim):
        pass

    def init_delivered_services(self, option, benefits):
        if (not hasattr(self, 'delivered_services')
            or not self.delivered_services):
            self.delivered_services = []
        else:
            self.delivered_services = list(self.delivered_services)
        for benefit in benefits:
            del_service = utils.instanciate_relation(self.__class__,
                'delivered_services')
            del_service.subscribed_service = option
            del_service.init_from_loss(self, benefit)
            self.delivered_services.append(del_service)


class ClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    loss = fields.Many2One('ins_claim.loss', 'Loss', ondelete='CASCADE')
    benefit = fields.Many2One('ins_product.benefit', 'Benefit',
        ondelete='RESTRICT',
        domain=[
            ('loss_descs', '=', Eval('_parent_loss', {}).get('loss_desc'))
        ], )
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

    def init_from_loss(self, loss, benefit):
        self.benefit = benefit

    def get_contract(self):
        return self.subscribed_service.get_contract()

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['date'] = self.loss.start_date
        cur_dict['start_date'] = self.loss.start_date
        cur_dict['end_date'] = self.loss.end_date
        cur_dict['loss'] = self.loss

    def calculate(self):
        cur_dict = {}
        self.init_dict_for_rule_engine(cur_dict)
        details_dict, errors = self.benefit.get_result('indemnification',
            cur_dict)
        if errors:
            return None, errors
        indemnification = utils.instanciate_relation(self.__class__,
            'indemnifications')
        indemnification.init_from_delivered_service(self)
        if not hasattr(self, 'indemnifications') or not self.indemnifications:
            self.indemnifications = []
        self.indemnifications.append(indemnification)
        indemnification.create_details_from_dict(details_dict)


class Indemnification(model.CoopSQL, model.CoopView):
    'Indemnification'

    __name__ = 'ins_claim.indemnification'

    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        ondelete='RESTRICT')
    customer = fields.Many2One('party.party', 'Customer', ondelete='RESTRICT')
    delivered_service = fields.Many2One('ins_contract.delivered_service',
        'Delivered Service', ondelete='CASCADE')
    kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Kind', sort=False),
        'get_kind')
    start_date = fields.Date('Start Date',
        states={'invisible': Eval('kind') != 'period'})
    end_date = fields.Date('End Date',
        states={'invisible': Eval('kind') != 'period'})
    status = fields.Selection(INDEMNIFICATION_STATUS, 'Status', sort=False)
    amount = fields.Numeric('Amount')
    details = fields.One2Many('ins_claim.indemnification_detail',
        'indemnification', 'Details')

    def init_from_delivered_service(self, delivered_service):
        self.status = 'calculated'
        self.start_date = delivered_service.loss.start_date
        self.end_date = delivered_service.loss.end_date
        self.customer = delivered_service.loss.claim.claimant
        self.beneficiary = delivered_service.loss.claim.claimant

    def get_kind(self, name=None):
        res = ''
        if not self.delivered_service:
            return res
        return self.delivered_service.benefit.indemnification_kind

    def create_details_from_dict(self, details_dict):
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            if not key in details_dict:
                continue
            detail = utils.instanciate_relation(self.__class__,
                'details')
            detail.init_from_indemnification(self)
            if not hasattr(self, 'details') or not self.details:
                self.details = []
            self.details.append(detail)
            detail.kind = key
            for field_name, value in details_dict[key].iteritems():
                setattr(detail, field_name, value)
        self.calculate_amount_from_details()

    def calculate_amount_from_details(self):
        self.amount = 0
        if not hasattr(self, 'details'):
            return
        for detail in self.details:
            detail.calculate_amount()
            print detail.amount
            self.amount += detail.amount


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
    amount_per_unit = fields.Numeric('Amount per Unit')
    nb_of_unit = fields.Numeric('Nb of Unit')
    unit = fields.Selection(date.DAILY_DURATION, 'Unit')
    amount = fields.Numeric('Amount')

    def init_from_indemnification(self, indemnification):
        pass

    def calculate_amount(self):
        print self.amount_per_unit
        print self.nb_of_unit
        self.amount = self.amount_per_unit * self.nb_of_unit


class DocumentRequest():
    'Document Request'

    __metaclass__ = PoolMeta

    __name__ = 'ins_product.document_request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()

        cls.needed_by = copy.copy(cls.needed_by)

        cls.needed_by.selection.append(
            ('ins_claim.claim', 'Claim'))
        cls.needed_by.selection.append(
            ('ins_contract.delivered_service', 'Delivered Service'))


class Document():
    'Document'

    __metaclass__ = PoolMeta

    __name__ = 'ins_product.document'

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()

        cls.for_object = copy.copy(cls.for_object)

        cls.for_object.selection.append(
            ('ins_claim.claim', 'Claim'))
        cls.for_object.selection.append(
            ('ins_contract.delivered_service', 'Delivered Service'))


class RequestFinder():
    'Request Finder'

    __metaclass__ = PoolMeta

    __name__ = 'ins_product.request_finder'

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({
            'ins_claim.claim': (
                'Claim', 'name')})
        return result


class ContactHistory():
    'Contact History'

    __metaclass__ = PoolMeta

    __name__ = 'party.contact_history'

    @classmethod
    def __setup__(cls):
        super(ContactHistory, cls).__setup__()
        cls.for_object_ref = copy.copy(cls.for_object_ref)

        cls.for_object_ref.selection.append(
            ['ins_claim.claim', 'Claim'])
