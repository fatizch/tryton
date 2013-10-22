#-*- coding:utf-8 -*-
import copy
import datetime
from decimal import Decimal

from trytond.pyson import Eval, Bool, Or, If
from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction

from trytond.modules.coop_utils import model, utils, coop_date, fields
from trytond.modules.coop_utils import coop_string
from trytond.modules.insurance_product.benefit import INDEMNIFICATION_KIND, \
    INDEMNIFICATION_DETAIL_KIND
from trytond.modules.insurance_product import Printable
from trytond.modules.offered.offered import DEF_CUR_DIG

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
    ('rejected', 'Rejected'),
    ('waiting_validation', 'Waiting Validation'),
    ('validated', 'Validated'),
    ('paid', 'Paid')
    ]

INDEMNIFICATION_STATUS = [
    ('calculated', 'Calculated'),
    ('validated', 'Validated'),
    ('rejected', 'Rejected'),
    ('paid', 'Paid'),
    ]


class Claim(model.CoopSQL, model.CoopView, Printable):
    'Claim'

    __name__ = 'claim.claim'
    _history = True

    name = fields.Char('Number', select=True,
        states={'readonly': True})
    status = fields.Selection(CLAIM_STATUS, 'Status', sort=False,
        states={'readonly': True})
    sub_status = fields.Selection('get_possible_sub_status',
        'Sub Status', selection_change_with=['status'],
        states={'readonly': True})
    reopened_reason = fields.Selection(CLAIM_REOPENED_REASON,
        'Reopened Reason', sort=False,
        states={'invisible': Eval('status') != 'reopened'})
    declaration_date = fields.Date('Declaration Date')
    end_date = fields.Date('End Date',
        states={'invisible': Eval('status') != 'closed', 'readonly': True})
    claimant = fields.Many2One('party.party', 'Claimant', ondelete='RESTRICT')
    losses = fields.One2Many('claim.loss', 'claim', 'Losses',
        states={'readonly': Eval('status') == 'closed'})
    documents = fields.One2Many('ins_product.document_request',
        'needed_by', 'Documents')
    # claim_history = fields.One2Many('claim.claim.history',
    #     'from_object', 'History')
    company = fields.Many2One('company.company', 'Company')
    #The Main contract is only used to ease the declaration process for 80%
    #of the claims where there is only one contract involved. This link should
    #not be used for other reason than initiating sub elements on claim.
    #Otherwise use claim.get_contract()
    main_contract = fields.Many2One('contract.contract', 'Main Contract',
        domain=[('id', 'in', Eval('possible_contracts')),
            ('company', '=', Eval('company'))],
        depends=['possible_contracts', 'company'])
    possible_contracts = fields.Function(
        fields.One2Many(
            'contract.contract', None, 'Contracts',
            on_change_with=['claimant', 'declaration_date']),
        'on_change_with_possible_contracts')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls.__rpc__.update({'get_possible_sub_status': RPC(instantiate=0)})

    @classmethod
    def write(cls, claims, values):
        for claim in claims:
            claim.update_sub_status()
            super(Claim, cls).write([claim], {'sub_status': claim.sub_status})
        super(Claim, cls).write(claims, values)

    def get_rec_name(self, name):
        res = super(Claim, self).get_rec_name(name)
        if self.claimant:
            res += ' %s' % self.claimant.get_rec_name(name)
        return res

    @classmethod
    def default_company(cls):
        return Transaction().context.get('company') or None

    def is_open(self):
        return self.status in ['open', 'reopened']

    def get_possible_sub_status(self):
        if self.status == 'closed':
            return CLAIM_CLOSED_REASON
        elif self.is_open():
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
        if 'rejected' in sub_statuses:
            return 'rejected'
        return 'instruction'

    def update_sub_status(self):
        sub_status = self.get_sub_status()
        if sub_status in [x[0] for x in self.get_possible_sub_status()]:
            self.sub_status = sub_status
        else:
            self.sub_status = ''

    @staticmethod
    def default_declaration_date():
        return utils.today()

    def init_loss(self):
        if hasattr(self, 'losses') and self.losses:
            return True
        loss = utils.instanciate_relation(self, 'losses')
        loss.init_from_claim(self)
        self.losses = [loss]
        return True

    def get_pending_relapse_loss(self):
        for loss in self.losses:
            if not loss.main_loss:
                continue
            if 'instruction' in loss.get_claim_sub_status():
                return loss

    def init_relapse_loss(self):
        if self.get_pending_relapse_loss():
            return True
        loss = utils.instanciate_relation(self, 'losses')
        loss.init_from_claim(self)
        self.losses = list(self.losses)
        self.losses.append(loss)
        return True

    def get_main_contact(self):
        return self.claimant

    def set_claim_number(self):
        if hasattr(self, 'name') and self.name:
            return True
        Generator = Pool().get('ir.sequence')
        good_gen, = Generator.search([
            ('code', '=', 'claim.claim'),
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

    @staticmethod
    def default_status():
        return 'open'

    @staticmethod
    def default_sub_status():
        return 'instruction'

    def close_claim(self, sub_status=None):
        self.status = 'closed'
        self.end_date = utils.today()
        return True, []

    def reopen_claim(self):
        if self.status == 'closed':
            self.status = 'reopened'
            self.end_date = None
        return True, []

    def complete_indemnifications(self):
        res = True, []
        for loss in self.losses:
            for delivered_service in loss.delivered_services:
                for indemnification in delivered_service.indemnifications:
                    utils.concat_res(res,
                        indemnification.complete_indemnification())
                pending_indemnification = False
                indemnification_paid = False
                for indemnification in delivered_service.indemnifications:
                    if indemnification.is_pending():
                        pending_indemnification = True
                    else:
                        indemnification_paid = True
                if indemnification_paid and not pending_indemnification:
                    delivered_service.status = 'delivered'
                    delivered_service.save()
        return res

    def get_possible_contracts(self, at_date=None):
        if not at_date:
            at_date = self.declaration_date
        Contract = Pool().get('contract.contract')
        return Contract.get_possible_contracts_from_party(self.claimant,
            at_date)

    def on_change_with_possible_contracts(self, name=None):
        return [x.id for x in self.get_possible_contracts()]

    def get_contracts(self):
        res = []
        for loss in self.losses:
            res.extend(loss.get_contracts())
        if not res and self.main_contract:
            res.append(self.main_contract)
        return list(set(res))

    def get_contract(self):
        contracts = self.get_contracts()
        if len(contracts) == 1:
            return contracts[0]
        elif len(contracts) > 1 and self.main_contract in contracts:
            return self.main_contract


class ClaimHistory(model.ObjectHistory):
    'Claim History'

    __name__ = 'claim.claim.history'

    name = fields.Char('Number')
    status = fields.Selection(CLAIM_STATUS, 'Status')
    sub_status = fields.Selection(list(set(CLAIM_CLOSED_REASON +
                CLAIM_OPEN_SUB_STATUS)),
        'Sub Status')
    declaration_date = fields.Date('Declaration Date')
    end_date = fields.Date('End Date',
        states={'invisible': Eval('status') != 'closed'})

    @classmethod
    def get_object_model(cls):
        return 'claim.claim'

    @classmethod
    def get_object_name(cls):
        return 'Claim'


class Loss(model.CoopSQL, model.CoopView):
    'Loss'

    __name__ = 'claim.loss'

    claim = fields.Many2One('claim.claim', 'Claim', ondelete='CASCADE')
    start_date = fields.Date('Loss Date')
    end_date = fields.Date('End Date', states={
            'invisible': Bool(~Eval('with_end_date')),
            'required': Bool(Eval('with_end_date')),
            }, depends=['with_end_date'],)
    loss_desc = fields.Many2One('ins_product.loss_desc', 'Loss Descriptor',
        ondelete='RESTRICT',
        on_change=['event_desc', 'loss_desc', 'with_end_date', 'end_date'],
        domain=[
            If(~~Eval('_parent_claim', {}).get('main_contract'),
                ('id', 'in', Eval('possible_loss_descs')), ())
            ],
        depends=['possible_loss_descs'])
    possible_loss_descs = fields.Function(
        fields.One2Many('ins_product.loss_desc', None, 'Possible Loss Descs',
            on_change_with=['claim']),
        'on_change_with_possible_loss_descs')
    event_desc = fields.Many2One('ins_product.event_desc', 'Event',
        domain=[('loss_descs', '=', Eval('loss_desc'))],
        states={'invisible': Bool(Eval('main_loss'))},
        depends=['loss_desc'], ondelete='RESTRICT')
    delivered_services = fields.One2Many(
        'contract.delivered_service', 'loss', 'Delivered Services',
        domain=[
            ('contract', 'in',
                Eval('_parent_claim', {}).get('possible_contracts'))
            ],)
    multi_level_view = fields.One2Many('contract.delivered_service',
        'loss', 'Delivered Services')
    main_loss = fields.Many2One('claim.loss', 'Main Loss',
        domain=[('claim', '=', Eval('claim')), ('id', '!=', Eval('id'))],
        depends=['claim', 'id'], ondelete='CASCADE',
        on_change=['main_loss', 'loss_desc'], states={
            'invisible': Eval('_parent_claim', {}).get('reopened_reason')
                != 'relapse'})
    sub_losses = fields.One2Many('claim.loss', 'main_loss', 'Sub Losses')
    with_end_date = fields.Function(
        fields.Boolean('With End Date'),
        'get_with_end_date')
    complementary_data = fields.Dict(
        'offered.complementary_data_def', 'Complementary Data',
        on_change_with=['loss_desc', 'complementary_data'],
        states={'invisible': ~Eval('complementary_data')})

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls._error_messages.update({
                'end_date_smaller_than_start_date':
                    'End Date is smaller than start date',
            })

    def get_with_end_date(self, name):
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
        res = ''
        if self.loss_desc:
            res = self.loss_desc.rec_name
        if self.start_date and not self.end_date:
            res += ' [%s]' % self.start_date
        elif self.start_date and self.end_date:
            res += ' [%s - %s]' % (self.start_date, self.end_date)
        if res:
            return res
        else:
            return super(Loss, self).get_rec_name(name)

    def get_claim_sub_status(self):
        res = []
        if self.delivered_services:
            for del_serv in self.delivered_services:
                res.extend(del_serv.get_claim_sub_status())
            return res
        else:
            return ['instruction']

    def on_change_main_loss(self):
        res = {}
        #TODO : Add possibility to have compatible loss example a disability
        #after a temporary incapacity
        if self.main_loss and self.main_loss.loss_desc:
            res['loss_desc'] = self.main_loss.loss_desc.id
            res['with_end_date'] = self.main_loss.loss_desc.with_end_date
        else:
            res['loss_desc'] = None
            res['with_end_date'] = False
        return res

    def on_change_loss_desc(self):
        res = {}
        res['with_end_date'] = self.get_with_end_date('')
        if (self.loss_desc and self.event_desc
                and not self.event_desc in self.loss_desc.event_descs):
            res['event_desc'] = None
        res['end_date'] = self.end_date if res['with_end_date'] else None
        return res

    @classmethod
    def validate(cls, instances):
        super(Loss, cls).validate(instances)
        for instance in instances:
            instance.check_end_date()

    def check_end_date(self):
        if (self.start_date and self.end_date
                and self.end_date < self.start_date):
            self.raise_user_error('end_date_smaller_than_start_date')

    def get_contracts(self):
        res = []
        for del_serv in self.delivered_services:
            if del_serv.contract:
                res.append(del_serv.contract)
        return list(set(res))

    def on_change_with_possible_loss_descs(self, name=None):
        res = []
        if not self.claim or not self.claim.main_contract:
            return res
        for benefit in self.claim.main_contract.get_possible_benefits(self):
            res.extend(benefit.loss_descs)
        return [x.id for x in set(res)]

    def get_all_complementary_data(self, at_date):
        res = {}
        if not utils.is_none(self, 'complementary_data'):
            res = self.complementary_data
        return res

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['loss'] = self
        #this date is the one used for finding the good rule,
        #so the rules that was effective when the loss occured
        cur_dict['date'] = self.start_date
        cur_dict['start_date'] = self.start_date
        if self.end_date:
            cur_dict['end_date'] = self.end_date


class ClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'contract.delivered_service'
    __metaclass__ = PoolMeta

    loss = fields.Many2One('claim.loss', 'Loss', ondelete='CASCADE')
    benefit = fields.Many2One(
        'ins_product.benefit', 'Benefit', ondelete='RESTRICT',
        domain=[
            If(~~Eval('_parent_loss', {}).get('loss_desc'),
                ('loss_descs', '=', Eval('_parent_loss', {}).get('loss_desc')),
                ())
            ], depends=['loss'])
    indemnifications = fields.One2Many(
        'claim.indemnification', 'delivered_service', 'Indemnifications',
        states={'invisible': ~Eval('indemnifications')})
    multi_level_view = fields.One2Many(
        'claim.indemnification', 'delivered_service', 'Indemnifications')
    complementary_data = fields.Dict(
        'offered.complementary_data_def', 'Complementary Data',
        on_change_with=['benefit', 'complementary_data'],
        states={'invisible': ~Eval('complementary_data')},)

    @classmethod
    def __setup__(cls):
        super(ClaimDeliveredService, cls).__setup__()
        utils.update_domain(cls, 'subscribed_service',
            [If(~~Eval('_parent_loss', {}).get('loss_desc'),
                ('offered.benefits.loss_descs', '=',
                    Eval('_parent_loss', {}).get('loss_desc')),
                ())
            ])
        utils.update_domain(cls, 'contract',
            [If(
                ~~Eval('_parent_loss', {}).get('_parent_claim', {}).get(
                    'main_contract'),
                ('id', '=', Eval('_parent_loss', {}).get(
                    '_parent_claim', {}).get('main_contract')),
                (),)
            ])

    def init_from_loss(self, loss, benefit):
        self.benefit = benefit
        self.complementary_data = self.on_change_with_complementary_data()

    def get_covered_data(self):
        #TODO : retrieve the good covered data
        for covered_data in self.subscribed_service.covered_data:
            return covered_data

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['delivered_service'] = self
        self.loss.init_dict_for_rule_engine(cur_dict)
        self.get_covered_data().init_dict_for_rule_engine(cur_dict)

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
                cur_dict['start_date'] = coop_date.add_day(indemn.end_date, 1)
                indemn, cur_err = self.create_indemnification(cur_dict)
                res = indemn is not None
                errs += cur_err
        for element in to_del:
            self.indemnifications.remove(element)
        Indemnification = Pool().get('claim.indemnification')
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

    @classmethod
    def calculate_delivered_services(cls, instances):
        for instance in instances:
            res, errs = instance.calculate()

    def calculate(self):
        cur_dict = {}
        self.init_dict_for_rule_engine(cur_dict)
        #We first check the eligibility of the benefit
        res, errs = self.benefit.get_result('eligibility', cur_dict)
        if errs:
            print errs
        self.func_error = None
        if res and not res.eligible:
            self.status = 'not_eligible'
            Error = Pool().get('rule_engine.error')
            func_err, other_errs = Error.get_functional_errors_from_errors(
                res.details)
            if func_err:
                self.func_error = func_err[0]
            return None, errs + other_errs
        currencies = self.get_local_currencies_used()
        for currency in currencies:
            cur_dict['currency'] = currency
            cur_res, cur_errs = self.create_indemnifications(cur_dict)
            res = res and cur_res
            errs += cur_errs
        self.status = 'calculated'
        if errs:
            print errs
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

    def get_all_complementary_data(self, at_date):
        res = {}
        if not utils.is_none(self, 'complementary_data'):
            res = self.complementary_data
        res.update(self.get_covered_data().get_all_complementary_data(at_date))
        res.update(self.loss.get_all_complementary_data(at_date))
        return res


class Indemnification(model.CoopView, model.CoopSQL, model.ModelCurrency):
    'Indemnification'

    __name__ = 'claim.indemnification'

    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        ondelete='RESTRICT',
        states={'readonly': Eval('status') == 'paid'})
    customer = fields.Many2One('party.party', 'Customer', ondelete='RESTRICT',
        states={'readonly': Eval('status') == 'paid'})
    delivered_service = fields.Many2One('contract.delivered_service',
        'Delivered Service', ondelete='CASCADE',
        states={'readonly': Eval('status') == 'paid'})
    kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Kind', sort=False,
            states={'invisible': True}),
        'get_kind')
    start_date = fields.Date('Start Date', states={
            'invisible': Eval('kind') != 'period',
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            })
    end_date = fields.Date('End Date', states={
            'invisible': Eval('kind') != 'period',
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            })
    status = fields.Selection(INDEMNIFICATION_STATUS, 'Status', sort=False,
        states={'readonly': Eval('status') == 'paid'})
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'],
        states={'readonly': Or(~Eval('manual'), Eval('status') == 'paid')})
    local_currency_amount = fields.Numeric('Local Currency Amount',
        digits=(16, Eval('local_currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': ~Eval('local_currency'),
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['local_currency_digits'])
    local_currency = fields.Many2One('currency.currency', 'Local Currency',
        states={
            'invisible': ~Eval('local_currency'),
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid')})
    local_currency_digits = fields.Function(
        fields.Integer('Local Currency Digits',
            states={'invisible': True},
            on_change_with=['local_currency']),
        'on_change_with_local_currency_digits')
    details = fields.One2Many('claim.indemnification_detail',
        'indemnification', 'Details',
        states={'readonly': Or(~Eval('manual'), Eval('status') == 'paid')})
    manual = fields.Boolean('Manual Calculation',
        states={'readonly': Eval('status') == 'paid'})

    @classmethod
    def __setup__(cls):
        super(Indemnification, cls).__setup__()
        cls.__rpc__.update({'validate_indemnification':
                    RPC(instantiate=0, readonly=False)})
        cls.__rpc__.update({'reject_indemnification':
                    RPC(instantiate=0, readonly=False)})
        cls._buttons.update(
            {
                'validate_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'reject_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
            })

    def init_from_delivered_service(self, delivered_service):
        self.status = 'calculated'
        #TODO : To enhance
        self.customer = delivered_service.loss.claim.claimant

    def get_kind(self, name=None):
        res = ''
        if not self.delivered_service:
            return res
        return self.delivered_service.benefit.indemnification_kind

    def get_beneficiary(self, beneficiary_kind, del_service):
        res = None
        if beneficiary_kind == 'subscriber':
            res = del_service.contract.get_policy_owner(
                del_service.loss.start_date)
        return res

    def create_details_from_dict(self, details_dict, del_service, currency):
        if utils.is_none(self, 'details'):
            self.details = []
        else:
            self.details = list(self.details)
            Pool().get('claim.indemnification_detail').delete(self.details)
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
                    #TODO: Temporary Hack
                    if (field_name == 'beneficiary_kind'
                            and utils.is_none(self, 'beneficiary')):
                        self.beneficiary = self.get_beneficiary(value,
                            del_service)
                    else:
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

    def on_change_with_local_currency_digits(self, name=None):
        if self.local_currency:
            return self.local_currency.digits
        return DEF_CUR_DIG

    def get_rec_name(self, name):
        return u'%s %s [%s]' % (
            coop_string.translate_value(self, 'start_date')
            if self.start_date else '',
            coop_string.amount_as_string(self.amount, self.currency),
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


class IndemnificationDetail(model.CoopSQL, model.CoopView,
        model.ModelCurrency):
    'Indemnification Detail'

    __name__ = 'claim.indemnification_detail'

    indemnification = fields.Many2One('claim.indemnification',
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
    unit = fields.Selection(coop_date.DAILY_DURATION, 'Unit')
    amount = fields.Numeric('Amount')

    def init_from_indemnification(self, indemnification):
        pass

    def calculate_amount(self):
        self.amount = self.amount_per_unit * self.nb_of_unit

    def get_currency(self):
        #If a local currency is used details are stored with the local currency
        #to make only one conversion at the indemnification level
        if self.indemnification:
            if self.indemnification.local_currency:
                return self.indemnification.local_currency
            else:
                return self.indemnification.currency


class DocumentRequest():
    'Document Request'

    __name__ = 'ins_product.document_request'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by = copy.copy(cls.needed_by)
        cls.needed_by.selection.append(('claim.claim', 'Claim'))
        cls.needed_by.selection.append(
            ('contract.delivered_service', 'Delivered Service'))


class Document():
    'Document'

    __name__ = 'ins_product.document'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(Document, cls).__setup__()
        cls.for_object = copy.copy(cls.for_object)
        cls.for_object.selection.append(('claim.claim', 'Claim'))
        cls.for_object.selection.append(
            ('contract.delivered_service', 'Delivered Service'))


class RequestFinder():
    'Request Finder'

    __name__ = 'ins_product.request_finder'
    __metaclass__ = PoolMeta

    @classmethod
    def allowed_values(cls):
        result = super(RequestFinder, cls).allowed_values()
        result.update({
            'claim.claim': (
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
        cls.for_object_ref.selection.append(['claim.claim', 'Claim'])


class IndemnificationDisplayer(model.CoopView):
    'Indemnification Displayer'

    __name__ = 'claim.indemnification_displayer'

    selection = fields.Selection([
        ('nothing', 'Nothing'), ('validate', 'Validate'),
        ('refuse', 'Refuse')], 'Selection')
    indemnification_displayer = fields.One2Many(
        'claim.indemnification', '', 'Indemnification',
        states={'readonly': True})
    indemnification = fields.Many2One(
        'claim.indemnification', 'Indemnification',
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
        'claim.claim', 'Claim', states={'readonly': True})
    claim_declaration_date = fields.Date('Claim Declaration Date')


class IndemnificationSelection(model.CoopView):
    'Indemnification Selection'

    __name__ = 'claim.indemnification_selection'

    indemnifications = fields.One2Many(
        'claim.indemnification_displayer', '', 'Indemnifications')
    domain_string = fields.Char(
        'Domain', states={'invisible': ~Eval('display_domain')},
        on_change=['domain_string', 'indemnifications', 'search_size'])
    modified = fields.Boolean(
        'Modified', states={'invisible': True},
        on_change_with=['indemnifications'])
    global_value = fields.Selection(
        [
            ('nothing', 'Nothing'), ('validate', 'Validate'),
            ('refuse', 'Refuse')],
        'Force Value', on_change=[
            'indemnifications', 'modified', 'apply', 'global_value'])
    display_domain = fields.Boolean('Display Search')
    search_size = fields.Integer(
        'Search Size', states={'invisible': ~Eval('display_domain')})

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
        Indemnification = Pool().get('claim.indemnification')
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
            field_name = clean_values[3 * i]
            operator = clean_values[3 * i + 1]
            operand = clean_values[3 * i + 2]
            if isinstance(Indemnification._fields[field_name], fields.Date):
                operand = datetime.date(*map(int, operand.split('-')))
            domain.append([
                'OR',
                [(field_name, '=', None)],
                [(field_name, operator, operand)]])
        return domain

    def on_change_global_value(self):
        result = []
        for elem in self.indemnifications:
            elem.selection = self.global_value
            if (hasattr(elem, 'id') and elem.id):
                elem.id = None
            elem_as_dict = model.serialize_this(elem)
            if 'id' in elem_as_dict:
                del elem_as_dict['id']
            result.append(elem_as_dict)
        return {'indemnifications': result}

    @classmethod
    def find_indemnifications(cls, domain, search_size):
        Indemnification = Pool().get('claim.indemnification')
        indemnifications = Indemnification.search(
            domain, order=[('start_date', 'ASC')], limit=search_size)
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
            self.build_domain(self.domain_string, self.search_size))

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

    __name__ = 'claim.indemnification_validation'

    start_state = 'select_indemnifications'

    select_indemnifications = StateView(
        'claim.indemnification_selection',
        'claim.indemnification_selection_form',
        [
            Button('Quit', 'end', 'tryton-cancel'),
            Button('Continue', 'reload_selection', 'tryton-refresh')])
    reload_selection = StateTransition()

    def default_select_indemnifications(self, fields):
        today = utils.today()
        default_max_date = datetime.date(today.year, today.month, 1)
        domain_string = 'status: = calculated, start_date: <= %s' % (
            coop_date.get_end_of_period(default_max_date, 'month'))
        Selector = Pool().get('claim.indemnification_selection')
        return {
            'domain_string': domain_string,
            'global_value': 'nothing',
            'search_size': 20,
            'indemnifications': Selector.find_indemnifications(
                Selector.build_domain(domain_string),
                20)['indemnifications']}

    def transition_reload_selection(self):
        claims = set([])
        to_validate = set([])
        to_reject = set([])
        for elem in self.select_indemnifications.indemnifications:
            if elem.selection == 'validate':
                to_validate.add(elem.indemnification.id)
                claims.add(elem.claim.id)
            elif elem.selection == 'refuse':
                to_reject.add(elem.indemnification.id)
                claims.add(elem.claim.id)
        Claim = Pool().get('claim.claim')
        Indemnification = Pool().get('claim.indemnification')
        Indemnification.validate_indemnification(
            Indemnification.browse(to_validate))
        Indemnification.reject_indemnification(
            Indemnification.browse(to_reject))
        for claim in Claim.browse(claims):
            claim.complete_indemnifications()
            Claim.write([claim], {})
        Selector = Pool().get('claim.indemnification_selection')
        self.select_indemnifications.indemnifications = \
            Selector.find_indemnifications(
                Selector.build_domain(
                    self.select_indemnifications.domain_string),
                self.select_indemnifications.search_size)['indemnifications']
        return 'select_indemnifications'
