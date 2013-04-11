#-*- coding:utf-8 -*-
import copy
import datetime
from decimal import Decimal

from trytond.pyson import Eval, Bool
from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.coop_utils import model, utils, date, fields, coop_string
from trytond.modules.coop_utils import abstract
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
    'ClaimHistory',
    'IndemnificationDisplayer',
    'IndemnificationSelection',
    'IndemnificationValidation',
]

CLAIM_STATUS = [
    ('open', 'Open'),
    ('closed', 'Closed'),
    ('reopened', 'Reopened'),
]

CLAIM_CLOSED_REASON = [
    ('', ''),
    ('rejected', 'Rejected'),
    ('paid', 'Paid'),
]

CLAIM_REOPENED_REASON = [
    ('', ''),
    ('relapse', 'Relapse'),
    ('reclamation', 'Reclamation'),
    ('regularization', 'Regularization')
]

CLAIM_OPEN_SUB_STATUS = [
    ('waiting_doc', 'Waiting For Documents'),
    ('instruction', 'Instruction'),
    ('waiting_validation', 'Waiting Validation'),
    ('validated', 'Validated'),
    ('paid', 'Paid')
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
    _history = True

    name = fields.Char('Number', select=True,
        states={'readonly': True})
    status = fields.Selection(CLAIM_STATUS, 'Status', sort=False,
        states={'readonly': True})
    sub_status = fields.Selection('get_possible_sub_status', 'Sub Status',
        selection_change_with=['status'], states={'readonly': True})
    declaration_date = fields.Date('Declaration Date')
    end_date = fields.Date('End Date',
        states={'invisible': Eval('status') != 'closed', 'readonly': True})
    claimant = fields.Many2One('party.party', 'Claimant')
    losses = fields.One2Many('ins_claim.loss', 'claim', 'Losses',
        states={'readonly': Eval('status') == 'closed'})
    documents = fields.One2Many('ins_product.document_request',
        'needed_by', 'Documents')
    claim_history = fields.One2Many('ins_claim.claim.history',
        'from_object', 'History')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls.__rpc__.update({'get_possible_sub_status': RPC(instantiate=0)})

    @classmethod
    def write(cls, claims, values):
        for claim in claims:
            claim.update_sub_status()
            values['sub_status'] = claim.sub_status
            super(Claim, cls).write([claim], values)
        super(Claim, cls).write(claims, values)

    def get_rec_name(self, name):
        res = super(Claim, self).get_rec_name(name)
        if self.claimant:
            res += ' %s' % self.claimant.get_rec_name(name)
        return res

    def get_possible_sub_status(self):
        if self.status == 'closed':
            return CLAIM_CLOSED_REASON
        elif self.status == 'reopened':
            return CLAIM_REOPENED_REASON
        elif self.status == 'open':
            return CLAIM_OPEN_SUB_STATUS
        return [('', '')]

    def is_waiting_for_documents(self):
        if not utils.is_none(self, 'documents'):
            for doc in self.documents:
                if not doc.is_complete:
                    return True
        return False

    def get_sub_status(self):
        if self.is_waiting_for_documents():
            return 'waiting_doc'
        sub_statuses = []
        for loss in self.losses:
            sub_statuses.extend(loss.get_claim_sub_status())
        if not sub_statuses:
            return 'instruction'
        if 'waiting_validation' in sub_statuses:
            return 'waiting_validation'
        if 'validated' in sub_statuses:
            return 'validated'
        if 'paid' in sub_statuses:
            return 'paid'
        print sub_statuses
        return 'instruction'

    def update_sub_status(self):
        self.sub_status = self.get_sub_status()

    @staticmethod
    def default_declaration_date():
        return utils.today()

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
        domain = [
            ('subscriber', '=', party.id),
            ('status_history.status', '=', 'active'),
            ('status_history.start_date', '<=', at_date),
            ['OR',
                [('status_history.end_date', '=', None)],
                [('status_history.end_date', '>=', at_date)]]
        ]
        return Contract.search(domain)

    @staticmethod
    def default_status():
        return 'open'

    @staticmethod
    def default_sub_status():
        return 'instruction'

    def close_claim(self, sub_status=None):
        #TODO : To Enhance. Get real closed reason
        self.status = 'closed'
        self.end_date = utils.today()
        return True, []

    def reopen_claim(self):
        if self.status == 'closed':
            self.status = 'reopened'
            self.sub_status = ''
            self.end_date = None
        return True, []


class ClaimHistory(model.ObjectHistory):
    'Claim History'

    __name__ = 'ins_claim.claim.history'

    name = fields.Char('Number')
    status = fields.Selection(CLAIM_STATUS, 'Status')
    sub_status = fields.Selection(CLAIM_CLOSED_REASON + CLAIM_REOPENED_REASON,
        'Sub Status')
    declaration_date = fields.Date('Declaration Date')
    end_date = fields.Date('End Date',
        states={'invisible': Eval('status') != 'closed'})

    @classmethod
    def get_object_model(cls):
        return 'ins_claim.claim'

    @classmethod
    def get_object_name(cls):
        return 'Claim'


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

    def get_claim_sub_status(self):
        res = []
        if self.delivered_services:
            for del_serv in self.delivered_services:
                res.extend(del_serv.get_claim_sub_status())
            return res
        else:
            return ['instruction']


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
        if self.loss.end_date:
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
        indemnification = utils.instanciate_relation(self, 'indemnifications')
        self.indemnifications.append(indemnification)
        indemnification.init_from_delivered_service(self)
        self.regularize_indemnification(indemnification, details_dict,
            cur_dict['currency'])
        indemnification.create_details_from_dict(details_dict, self,
            cur_dict['currency'])
        return indemnification, errors

    def create_indemnifications(self, cur_dict):
        if not hasattr(self, 'indemnifications') or not self.indemnifications:
            self.indemnifications = []
        else:
            self.indemnifications = list(self.indemnifications)
        to_del = [x for x in self.indemnifications if x.status == 'calculated']
        indemn, errs = self.create_indemnification(cur_dict)
        res = indemn is not None
        if ('end_date' in cur_dict and res
                and indemn.end_date < cur_dict['end_date']):
            while res and indemn.end_date < cur_dict['end_date']:
                cur_dict = cur_dict.copy()
                cur_dict['start_date'] = date.add_day(indemn.end_date, 1)
                indemn, cur_err = self.create_indemnification(cur_dict)
                res = indemn is not None
                errs += cur_err
        for element in to_del:
            self.indemnifications.remove(element)
        Indemnification = Pool().get('ins_claim.indemnification')
        Indemnification.delete(to_del)
        return res, errs

    def regularize_indemnification(self, indemn, details_dict, currency):
        amount = Decimal(0)
        for other_indemn in self.indemnifications:
            if (other_indemn.status == 'paid'
                    and other_indemn.currency == currency):
                amount += other_indemn.amount
        if amount:
            details_dict['regularization'] = [
                {
                    'amount_per_unit': amount,
                    'nb_of_unit': -1,
                }]

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
            cur_res, cur_errs = self.create_indemnifications(cur_dict)
            res = res and cur_res
            errs += cur_errs
        self.status = 'calculated'
        return res, errs

    def get_rec_name(self, name=None):
        if self.benefit:
            res = self.benefit.get_rec_name(name)
            if self.status:
                res += ' [%s]' % coop_string.translate_value(self, 'status')
            return res
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
                    and (utils.is_none(indemn, 'local_currency')
                        or indemn.local_currency == cur_dict['currency'])):
                return indemn

    def get_currency(self):
        if self.subscribed_service:
            return self.subscribed_service.get_currency()

    def get_claim_sub_status(self):
        if self.indemnifications:
            return [x.get_claim_sub_status() for x in self.indemnifications]
        elif self.status == 'not_eligible':
            return ['rejected']
        else:
            return ['instruction']


class Indemnification(model.CoopView, model.CoopSQL):
    'Indemnification'

    __name__ = 'ins_claim.indemnification'

    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        ondelete='RESTRICT')
    customer = fields.Many2One('party.party', 'Customer', ondelete='RESTRICT')
    delivered_service = fields.Many2One('ins_contract.delivered_service',
        'Delivered Service', ondelete='CASCADE')
    kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Kind', sort=False,
            states={'invisible': True}),
        'get_kind')
    start_date = fields.Date('Start Date',
        states={
            'invisible': Eval('kind') != 'period',
            'readonly': ~Eval('manual'), })
    end_date = fields.Date('End Date',
        states={
            'invisible': Eval('kind') != 'period',
            'readonly': ~Eval('manual'), })
    status = fields.Selection(INDEMNIFICATION_STATUS, 'Status', sort=False,
        states={
            'invisible': Eval('status') == 'calculated',
            'readonly': True})
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'],
        states={'readonly': ~Eval('manual')})
    currency = fields.Function(
        fields.Many2One('currency.currency', 'Currency'),
        'get_currency_id')
    currency_digits = fields.Function(
        fields.Integer('Currency Digits', states={'invisible': True}),
        'get_currency_digits')
    local_currency_amount = fields.Numeric('Local Currency Amount',
        digits=(16, Eval('local_currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': ~Eval('local_currency'),
            'readonly': ~Eval('manual')},
        depends=['local_currency_digits'])
    local_currency = fields.Many2One('currency.currency', 'Local Currency',
        states={'invisible': ~Eval('local_currency')})
    local_currency_digits = fields.Function(
        fields.Integer('Local Currency Digits',
            states={'invisible': True},
            on_change_with=['local_currency']),
        'on_change_with_local_currency_digits')
    details = fields.One2Many('ins_claim.indemnification_detail',
        'indemnification', 'Details', states={'readonly': ~Eval('manual')})
    manual = fields.Boolean('Manual Calculation')

    @classmethod
    def __setup__(cls):
        super(Indemnification, cls).__setup__()
        cls.__rpc__.update({'validate_indemnification': RPC(instantiate=0,
            readonly=False)})
        cls.__rpc__.update({'reject_indemnification': RPC(instantiate=0)})
        cls._buttons.update(
            {
                'validate_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'reject_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
            })

    def init_from_delivered_service(self, delivered_service):
        self.status = 'calculated'
        self.customer = delivered_service.loss.claim.claimant
        self.beneficiary = delivered_service.loss.claim.claimant

    def get_kind(self, name=None):
        res = ''
        if not self.delivered_service:
            return res
        return self.delivered_service.benefit.indemnification_kind

    def create_details_from_dict(self, details_dict, del_service, currency):
        if utils.is_none(self, 'details'):
            self.details = []
        else:
            self.details = list(self.details)
            Pool().get('ins_claim.indemnification_detail').delete(self.details)
            self.details[:] = []
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            if not key in details_dict:
                continue
            for detail_dict in details_dict[key]:
                detail = utils.instanciate_relation(self, 'details')
                detail.init_from_indemnification(self)
                self.details.append(detail)
                detail.kind = key
                for field_name, value in detail_dict.iteritems():
                    setattr(detail, field_name, value)
                if ('start_date' in detail_dict
                        and (utils.is_none(self, 'start_date')
                            or detail.start_date < self.start_date)):
                    self.start_date = detail.start_date
        self.calculate_amount_and_end_date_from_details(del_service, currency)

    def calculate_amount_and_end_date_from_details(self, del_service,
            currency):
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
            if hasattr(detail, 'end_date'):
                self.end_date = detail.end_date
        if self.local_currency_amount > 0:
            Currency = Pool().get('currency.currency')
            self.amount = Currency.compute(self.local_currency,
                self.local_currency_amount, main_currency)
        self.amount = main_currency.round(self.amount)

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
            coop_string.translate_value(self, 'start_date')
            if self.start_date else '',
            self.amount,
            coop_string.translate_value(self, 'status') if self.status else '',
        )

    def complete_indemnification(self):
        if self.status == 'validated' and self.amount:
            self.status = 'paid'
            self.save()
        return True, []

    def is_pending(self):
        return self.amount > 0 and self.status not in ['paid', 'rejected']

    def get_claim_sub_status(self):
        if self.status == 'calculated':
            return 'waiting_validation'
        elif self.status == 'validated':
            return 'validated'
        elif self.status == 'paid':
            return 'paid'
        else:
            return 'instruction'

    @classmethod
    def validate_indemnification(cls, indemnifications):
        cls.write(indemnifications, {'status': 'validated'})

    @classmethod
    def reject_indemnification(cls, indemnifications):
        cls.write(indemnifications, {'status': 'rejected'})


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


class IndemnificationDisplayer(model.CoopView):
    'Indemnification Displayer'

    __name__ = 'ins_claim.indemnification_displayer'

    selection = fields.Selection([
        ('nothing', 'Nothing'), ('validate', 'Validate'),
        ('refuse', 'Refuse')], 'Selection')
    indemnification_displayer = fields.One2Many(
        'ins_claim.indemnification', '', 'Indemnification',
        states={'readonly': True})
    indemnification = fields.Many2One(
        'ins_claim.indemnification', 'Indemnification',
        states={'invisible': True, 'readonly': True})
    amount = fields.Numeric(
        'Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'],
        states={'readonly': True})
    currency_digits = fields.Function(
        fields.Integer('Currency Digits', states={'invisible': True}),
        'getter_void', 'setter_void')
    start_date = fields.Date('Start Date', states={'readonly': True})
    end_date = fields.Date('End Date', states={'readonly': True})
    covered_element = fields.Char('Covered Element', states={'readonly': True})
    claim_number = fields.Char('Claim Number', states={'readonly': True})
    claim = fields.Many2One(
        'ins_claim.claim', 'Claim', states={'readonly': True})
    claim_declaration_date = fields.Date('Claim Declaration Date')


class IndemnificationSelection(model.CoopView):
    'Indemnification Selection'

    __name__ = 'ins_claim.indemnification_selection'

    indemnifications = fields.One2Many(
        'ins_claim.indemnification_displayer', '', 'Indemnifications')
    domain_string = fields.Char(
        'Domain', on_change=['domain_string', 'indemnifications'],
        states={'invisible': ~Eval('display_domain')})
    modified = fields.Boolean(
        'Modified', states={'invisible': True},
        on_change_with=['indemnifications'])
    apply = fields.Boolean(
        'Apply on all', on_change=[
            'indemnifications', 'modified', 'apply', 'global_value'])
    global_value = fields.Selection([
        ('nothing', 'Nothing'), ('validate', 'Validate'),
        ('refuse', 'Refuse')], 'Global Value')
    display_domain = fields.Boolean('Display Search')

    @classmethod
    def __setup__(cls):
        super(IndemnificationSelection, cls).__setup__()
        cls._error_messages.update({
            'indemnifications_selected':
            'Please unselect all indemnifications first',
        })

    @classmethod
    def build_domain(cls, string):
        if not string:
            return []
        Indemnification = Pool().get('ins_claim.indemnification')
        clean_values = []
        cur_value = ''
        quote_found = False
        for elem in string:
            if elem == '"':
                if quote_found:
                    clean_values.append(cur_value)
                    cur_value = ''
                    quote_found = False
                else:
                    quote_found = True
            elif elem == ' ' or elem == ':' or elem == ',':
                if cur_value and not quote_found:
                    clean_values.append(cur_value)
                    cur_value = ''
            else:
                cur_value += elem
        if cur_value:
            clean_values.append(cur_value)
        domain = []
        for i in range(len(clean_values) / 3):
            field_name = clean_values[3*i]
            operator = clean_values[3*i+1]
            operand = clean_values[3*i+2]
            if isinstance(Indemnification._fields[field_name], fields.Date):
                operand = datetime.date(*map(int, operand.split('-')))
            domain.append([
                'OR',
                [(field_name, '=', None)],
                [(field_name, operator, operand)]])
        return domain

    def on_change_apply(self):
        result = []
        for elem in self.indemnifications:
            elem.selection = self.global_value
            if (hasattr(elem, 'id') and elem.id):
                elem.id = None
            elem_as_dict = abstract.WithAbstract.serialize_field(elem)
            if 'id' in elem_as_dict:
                del elem_as_dict['id']
            result.append(elem_as_dict)
        return {'indemnifications': result, 'apply': False}

    @classmethod
    def find_indemnifications(cls, domain):
        Indemnification = Pool().get('ins_claim.indemnification')
        indemnifications = Indemnification.search(
            domain, order=[('start_date', 'ASC')], limit=20)
        result = []
        for indemnification in indemnifications:
            claim = indemnification.delivered_service.loss.claim
            result.append({
                'selection': 'nothing',
                'indemnification': indemnification.id,
                'amount': indemnification.amount,
                'start_date': indemnification.start_date,
                'end_date': indemnification.end_date,
                'indemnification_displayer': [indemnification.id],
                'which_display': 'indemnification',
                'claim': claim.id,
                'claim_declaration_date': claim.declaration_date,
                'claim_number': '%s' % claim.name,
                'covered_element': '%s' % (
                    indemnification.customer.get_rec_name(None))})
        return {'indemnifications': result, 'modified': False}

    def on_change_domain_string(self):
        return self.find_indemnifications(
            self.build_domain(self.domain_string))

    def on_change_with_modified(self):
        if not (hasattr(self, 'indemnifications') and self.indemnifications):
            return
        for indemnification in self.indemnifications:
            if (hasattr(indemnification, 'selection') and
                    indemnification.selection != 'nothing'):
                return True
        return False


class IndemnificationValidation(Wizard):
    'Indemnification Validation'

    __name__ = 'ins_claim.indemnification_validation'

    start_state = 'select_indemnifications'

    select_indemnifications = StateView(
        'ins_claim.indemnification_selection',
        'insurance_claim.indemnification_selection_form',
        [
            Button('Quit', 'end', 'tryton-cancel'),
            Button('Continue', 'reload_selection', 'tryton-refresh')])
    reload_selection = StateTransition()

    def default_select_indemnifications(self, fields):
        today = utils.today()
        default_max_date = datetime.date(today.year, today.month, 1)
        domain_string = 'status: = calculated, start_date: <= %s' % (
            date.get_end_of_period(default_max_date, 1, 'month'))
        Selector = Pool().get('ins_claim.indemnification_selection')
        return {
            'domain_string': domain_string,
            'global_value': 'nothing',
            'indemnifications': Selector.find_indemnifications(
                Selector.build_domain(domain_string))['indemnifications']}

    def transition_reload_selection(self):
        claims = set([])
        for elem in self.select_indemnifications.indemnifications:
            if elem.selection == 'validated':
                elem.indemnification.validate_indemnification()
                claims.add(elem.claim_displayer[0].id)
            elif elem.selection == 'refused':
                elem.indemnification.reject_indemnification()
                claims.add(elem.claim_displayer[0].id)
        Claim = Pool().get('ins_claim.claim')
        for claim in Claim.browse(claims):
            claim.complete_indemnification()
        Selector = Pool().get('ins_claim.indemnification_selection')
        self.select_indemnifications.indemnifications = \
            Selector.find_indemnifications(
                Selector.build_domain(
                    self.select_indemnifications.domain_string))[
                        'indemnifications']
        return 'select_indemnifications'
