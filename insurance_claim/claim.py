#-*- coding:utf-8 -*-
import copy
from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta, Pool

from trytond.modules.coop_utils import model, utils, date, fields, coop_string
from trytond.modules.insurance_product.benefit import INDEMNIFICATION_KIND, \
    INDEMNIFICATION_DETAIL_KIND
from trytond.modules.insurance_product import Printable
from trytond.modules.insurance_product.product import DEF_CUR_DIG

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
    ('', ''),
    ('refusal', 'Refusal'),
    ('paid', 'Paid'),
]


INDEMNIFICATION_STATUS = [
    ('calculated', 'Calculated'),
    ('validated', 'Validated'),
    ('refused', 'Refused'),
    ('paid', 'Paid'),
]


class Claim(model.CoopSQL, model.CoopView, Printable):
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
        return ''

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
        if hasattr(self, 'name') and self.name:
            return True
        Generator = Pool().get('ir.sequence')
        good_gen, = Generator.search([
            ('code', '=', 'ins_claim.claim'),
        ], limit=1)
        self.name = good_gen.get_id(good_gen.id)
        return True

    def get_contact(self):
        return self.claimant

    def get_main_loss(self):
        if not self.losses:
            return None
        return self.losses[0]

    def get_main_contract(self):
        loss = self.get_main_loss()
        if not loss or not loss.delivered_services:
            return None
        delivered_service = loss.delivered_services[0]
        return delivered_service.subscribed_service.contract

    def get_sender(self):
        contract = self.get_main_contract()
        if not contract:
            return None
        good_role = contract.get_management_role('claim_manager')
        if not good_role:
            return None
        return good_role.protocol.party

    @classmethod
    def get_possible_contracts_from_party(cls, party, at_date):
        if not party:
            return []
        Contract = Pool().get('ins_contract.contract')
        #TODO: filter with the at_date
        return Contract.search([('subscriber', '=', party.id)])

    def close_claim(self):
        self.status = 'closed'
        self.sub_status = 'paid'
        self.end_date = utils.today()
        return True


class Loss(model.CoopSQL, model.CoopView):
    'Loss'

    __name__ = 'ins_claim.loss'

    claim = fields.Many2One('ins_claim.claim', 'Claim', ondelete='CASCADE')
    start_date = fields.Date('Loss Date')
    end_date = fields.Date('End Date',
        states={
            'invisible': Bool(~Eval('with_end_date')),
            'required': Bool(Eval('with_end_date')),
        }, depends=['with_end_date'])
    loss_desc = fields.Many2One('ins_product.loss_desc', 'Loss Descriptor',
        ondelete='RESTRICT')
    event_desc = fields.Many2One('ins_product.event_desc', 'Event',
        domain=[
            ('loss_descs', '=', Eval('loss_desc'))
        ],
        depends=['loss_desc'], ondelete='RESTRICT')
    delivered_services = fields.One2Many(
        'ins_contract.delivered_service', 'loss', 'Delivered Services')
    multi_level_view = fields.One2Many(
        'ins_contract.delivered_service', 'loss', 'Delivered Services')
    main_loss = fields.Many2One(
        'ins_claim.loss', 'Main Loss', ondelete='CASCADE')
    sub_losses = fields.One2Many('ins_claim.loss', 'main_loss', 'Sub Losses')
    with_end_date = fields.Function(
        fields.Boolean('With End Date', on_change_with=['loss_desc']),
        'on_change_with_with_end_date')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data',
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
            del_service = None
            for other_del_service in self.delivered_services:
                if (other_del_service.benefit == benefit
                        and other_del_service.subscribed_service == option):
                    del_service = other_del_service
            if del_service:
                continue
            del_service = utils.instanciate_relation(self.__class__,
                'delivered_services')
            del_service.subscribed_service = option
            del_service.init_from_loss(self, benefit)
            self.delivered_services.append(del_service)

    def get_rec_name(self, name=None):
        if self.loss_desc:
            return self.loss_desc.get_rec_name(name)
        return super(Loss, self).get_rec_name(name)


class ClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    loss = fields.Many2One('ins_claim.loss', 'Loss', ondelete='CASCADE')
    benefit = fields.Many2One(
        'ins_product.benefit', 'Benefit', ondelete='RESTRICT',
        domain=[
            ('loss_descs', '=', Eval('_parent_loss', {}).get('loss_desc'))])
    indemnifications = fields.One2Many(
        'ins_claim.indemnification', 'delivered_service', 'Indemnifications',
        states={'invisible': ~Eval('indemnifications')})
    multi_level_view = fields.One2Many(
        'ins_claim.indemnification', 'delivered_service', 'Indemnifications')
    complementary_data = fields.Dict(
        'ins_product.complementary_data_def', 'Complementary Data',
        on_change_with=['benefit', 'complementary_data'],
        states={'invisible': Eval('status') == 'applicable'})

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
        self.complementary_data = self.on_change_with_complementary_data()

    def get_contract(self):
        return self.subscribed_service.get_contract()

    def get_covered_data(self):
        for covered_data in self.subscribed_service.covered_data:
            return covered_data

    def init_dict_for_rule_engine(self, cur_dict):
        #this date is the one used for finding the good rule,
        #so the rules that was effective when the loss occured
        cur_dict['date'] = self.loss.start_date
        cur_dict['start_date'] = self.loss.start_date
        cur_dict['end_date'] = self.loss.end_date
        cur_dict['loss'] = self.loss
        cur_dict['option'] = self.subscribed_service
        cur_dict['delivered_service'] = self
        cur_dict['data'] = self.get_covered_data()
        cur_dict['subscriber'] = self.get_contract().get_policy_owner()

    def get_local_currencies_used(self):
        res = []
        res.append(self.get_currency())
        res += [x.currency for x in self.expenses]
        return tuple(res)

    def create_indemnification(self, cur_dict):
        details_dict, errors = self.benefit.get_result('indemnification',
            cur_dict)
        if errors:
            return None, errors
        #TODO : To enhance
        indemnification = self.get_indemnification_being_calculated(cur_dict)
        if not hasattr(self, 'indemnifications') or not self.indemnifications:
            self.indemnifications = []
        else:
            self.indemnifications = list(self.indemnifications)
        if not indemnification:
            indemnification = utils.instanciate_relation(
                self.__class__, 'indemnifications')
            self.indemnifications.append(indemnification)
        indemnification.init_from_delivered_service(self)
        indemnification.create_details_from_dict(details_dict, self,
            cur_dict['currency'])
        return True, errors

    def calculate(self):
        cur_dict = {}
        self.init_dict_for_rule_engine(cur_dict)
        #We first check the eligibility of the benefit
        res, errs = self.benefit.get_result('eligibility', cur_dict)
        if res and not res.eligible:
            self.status = 'not_eligible'
            return None, errs
        currencies = self.get_local_currencies_used()
        for currency in currencies:
            cur_dict['currency'] = currency
            cur_res, cur_errs = self.create_indemnification(cur_dict)
            res = res and cur_res
            errs += cur_errs
        self.status = 'calculated'
        return res, errs

    def get_rec_name(self, name=None):
        if self.benefit:
            return self.benefit.get_rec_name(name)
        return super(ClaimDeliveredService, self).get_rec_name(name)

    def on_change_with_complementary_data(self):
        return utils.init_complementary_data(self.get_complementary_data_def())

    def get_complementary_data_def(self):
        if self.benefit:
            return self.benefit.complementary_data_def

    def get_complementary_data_value(self, at_date, value):
        return utils.get_complementary_data_value(self, 'complementary_data',
            self.get_complementary_data_def(), at_date, value)

    def get_indemnification_being_calculated(self, cur_dict):
        if not hasattr(self, 'indemnifications'):
            return None
        for indemn in self.indemnifications:
            if (indemn.status == 'calculated'
                    and (not hasattr(indemn, 'local_currency')
                        or indemn.local_currency == cur_dict['currency'])):
                return indemn

    def get_currency(self):
        if self.subscribed_service:
            return self.subscribed_service.get_currency()


class Indemnification(model.CoopView, model.CoopSQL):
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
    amount = fields.Numeric('Amount',
        #digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        #depends=['currency_digits']
        )
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')
    local_currency_amount = fields.Numeric('Local Currency Amount',
        digits=(16, Eval('local_currency_digits', DEF_CUR_DIG)),
        states={'invisible': ~Eval('local_currency')},
        depends=['local_currency_digits'])
    local_currency = fields.Many2One('currency.currency', 'Local Currency',
        states={'invisible': ~Eval('local_currency')})
    local_currency_digits = fields.Function(
        fields.Integer('Local Currency Digits',
            on_change_with=['local_currency']),
        'on_change_with_local_currency_digits')
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

    def create_details_from_dict(self, details_dict, del_service, currency):
        if not hasattr(self, 'details'):
            self.details = []
        else:
            self.details = list(self.details)
            #TODO: Delete previous details
            self.details[:] = []
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            if not key in details_dict:
                continue
            for detail_dict in details_dict[key]:
                detail = utils.instanciate_relation(self.__class__,
                    'details')
                detail.init_from_indemnification(self)
                self.details.append(detail)
                detail.kind = key
                for field_name, value in detail_dict.iteritems():
                    setattr(detail, field_name, value)
        self.calculate_amount_from_details(del_service, currency)

    def calculate_amount_from_details(self, del_service, currency):
        self.amount = 0
        self.local_currency_amount = 0
        if not hasattr(self, 'details'):
            return
        main_currency = del_service.get_currency()
        for detail in self.details:
            detail.calculate_amount()
            if currency == main_currency:
                self.amount += detail.amount
            else:
                self.local_currency_amount += detail.amount
                self.local_currency = currency
        if self.local_currency_amount > 0:
            Currency = Pool().get('currency.currency')
            self.amount = Currency.compute(self.local_currency,
                self.local_currency_amount, main_currency)

    def get_currency(self):
        if self.delivered_service:
            return self.delivered_service.get_currency()

    def get_currency_id(self, name):
        currency = self.get_currency()
        if currency:
            return currency.id

    def get_currency_digits(self, name):
        currency = self.get_currency()
        if currency:
            return currency.digits
        return DEF_CUR_DIG

    def on_change_with_local_currency_digits(self, name=None):
        if self.local_currency:
            return self.local_currency.digits
        return DEF_CUR_DIG

    def get_rec_name(self, name):
        return '%s %.2f [%s]' % (
            coop_string.translate_value(self, 'start_date'),
            self.amount,
            coop_string.translate_value(self, 'status') if self.status else '',
        )


class IndemnificationDetail(model.CoopSQL, model.CoopView):
    'Indemnification Detail'

    __name__ = 'ins_claim.indemnification_detail'

    indemnification = fields.Many2One('ins_claim.indemnification',
        'Indemnification', ondelete='CASCADE')
    start_date = fields.Date('Start Date', states={
            'invisible':
                Eval('_parent_indemnification', {}).get('kind') != 'period'
    })
    end_date = fields.Date('End Date', states={
            'invisible':
                Eval('_parent_indemnification', {}).get('kind') != 'period'
    })
    kind = fields.Selection(INDEMNIFICATION_DETAIL_KIND, 'Kind', sort=False)
    amount_per_unit = fields.Numeric('Amount per Unit')
    nb_of_unit = fields.Numeric('Nb of Unit')
    unit = fields.Selection(date.DAILY_DURATION, 'Unit')
    amount = fields.Numeric('Amount')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits'),
        'get_currency_digits')

    def init_from_indemnification(self, indemnification):
        pass

    def calculate_amount(self):
        self.amount = self.amount_per_unit * self.nb_of_unit

    def get_currency(self):
        if self.indemnification:
            return self.indemnification.get_currency()

    def get_currency_digits(self):
        currency = self.get_currency
        if currency:
            return currency.digits


class DocumentRequest():
    'Document Request'

    __name__ = 'ins_product.document_request'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by = copy.copy(cls.needed_by)
        cls.needed_by.selection.append(('ins_claim.claim', 'Claim'))
        cls.needed_by.selection.append(
            ('ins_contract.delivered_service', 'Delivered Service'))


class Document():
    'Document'

    __name__ = 'ins_product.document'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        cls.for_object = copy.copy(cls.for_object)
        cls.for_object.selection.append(('ins_claim.claim', 'Claim'))
        cls.for_object.selection.append(
            ('ins_contract.delivered_service', 'Delivered Service'))


class RequestFinder():
    'Request Finder'

    __name__ = 'ins_product.request_finder'
    __metaclass__ = PoolMeta

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({
            'ins_claim.claim': (
                'Claim', 'name')})
        return result


class ContactHistory():
    'Contact History'

    __name__ = 'party.contact_history'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(ContactHistory, cls).__setup__()
        cls.for_object_ref = copy.copy(cls.for_object_ref)
        cls.for_object_ref.selection.append(['ins_claim.claim', 'Claim'])
