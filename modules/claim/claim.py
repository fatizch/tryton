import datetime
from decimal import Decimal

from trytond.pyson import Eval, Bool, Or, If
from trytond.pool import PoolMeta, Pool
from trytond.rpc import RPC
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.transaction import Transaction

from trytond.modules.cog_utils import model, utils, coop_date, fields
from trytond.modules.cog_utils import coop_string
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.benefit.benefit import INDEMNIFICATION_DETAIL_KIND
from trytond.modules.benefit.benefit import INDEMNIFICATION_KIND
from trytond.modules.offered_insurance import Printable
from trytond.modules.currency_cog.currency import DEF_CUR_DIG


__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    'Loss',
    'DeliveredService',
    'Indemnification',
    'IndemnificationDetail',
    'ClaimIndemnificationValidateDisplay',
    'ClaimIndemnificationValidateSelect',
    'ClaimIndemnificationValidate',
    ]


class Claim(model.CoopSQL, model.CoopView, Printable):
    'Claim'

    __name__ = 'claim'
    _history = True

    name = fields.Char('Number', select=True, states={'readonly': True})
    status = fields.Selection([
            ('open', 'Open'),
            ('closed', 'Closed'),
            ('reopened', 'Reopened'),
            ], 'Status', sort=False, states={'readonly': True})
    sub_status = fields.Selection('get_possible_sub_status', 'Sub Status',
        states={'readonly': True})
    reopened_reason = fields.Selection([
            ('', ''),
            ('relapse', 'Relapse'),
            ('reclamation', 'Reclamation'),
            ('regularization', 'Regularization')
            ], 'Reopened Reason', sort=False,
        states={'invisible': Eval('status') != 'reopened'})
    declaration_date = fields.Date('Declaration Date')
    end_date = fields.Date('End Date', states={
            'invisible': Eval('status') != 'closed',
            'readonly': True,
            })
    claimant = fields.Many2One('party.party', 'Claimant', ondelete='RESTRICT')
    losses = fields.One2Many('claim.loss', 'claim', 'Losses',
        states={'readonly': Eval('status') == 'closed'})
    documents = fields.One2Many('document.request', 'needed_by', 'Documents')
    company = fields.Many2One('company.company', 'Company',
        ondelete='RESTRICT')
    # The Main contract is only used to ease the declaration process for 80%
    # of the claims where there is only one contract involved. This link should
    # not be used for other reason than initiating sub elements on claim.
    # Otherwise use claim.get_contract()
    main_contract = fields.Many2One('contract', 'Main Contract',
        ondelete='RESTRICT', domain=[('id', 'in', Eval('possible_contracts')),
            ('company', '=', Eval('company'))],
        depends=['possible_contracts', 'company'])
    possible_contracts = fields.Function(
        fields.One2Many('contract', None, 'Contracts'),
        'on_change_with_possible_contracts')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls.__rpc__.update({'get_possible_sub_status': RPC(instantiate=0)})
        cls._error_messages.update({
                'no_main_contract': 'Impossible to find a main contract, '
                'please try again once it has been set',
                })

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

    @fields.depends('status')
    def get_possible_sub_status(self):
        if self.status == 'closed':
            return [
                ('', ''),
                ('rejected', 'Rejected'),
                ('paid', 'Paid'),
                ]
        elif self.is_open():
            return [
                ('waiting_doc', 'Waiting For Documents'),
                ('instruction', 'Instruction'),
                ('rejected', 'Rejected'),
                ('waiting_validation', 'Waiting Validation'),
                ('validated', 'Validated'),
                ('paid', 'Paid'),
                ]
        return [('', '')]

    def is_waiting_for_documents(self):
        if getattr(self, 'documents', None):
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

    def update_services_extra_data(self):
        for loss in self.losses:
            for service in loss.services:
                service.on_change_extra_data()
                service.save()
        return True

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
        Loss = Pool().get('claim.loss')
        loss = Loss()
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
        Loss = Pool().get('claim.loss')
        loss = Loss()
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
            ('code', '=', 'claim'),
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
        if not loss or not loss.services:
            return None
        service = loss.services[0]
        return service.option.contract

    def get_sender(self):
        contract = self.get_main_contract()
        if not contract:
            return None
        good_role = contract.get_agreement('claim_manager')
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
            for service in loss.services:
                for indemnification in service.indemnifications:
                    utils.concat_res(res,
                        indemnification.complete_indemnification())
                pending_indemnification = False
                indemnification_paid = False
                for indemnification in service.indemnifications:
                    if indemnification.is_pending():
                        pending_indemnification = True
                    else:
                        indemnification_paid = True
                if indemnification_paid and not pending_indemnification:
                    service.status = 'delivered'
                    service.save()
        return res

    def get_possible_contracts(self, at_date=None):
        if not at_date:
            at_date = self.declaration_date
        Contract = Pool().get('contract')
        return Contract.get_possible_contracts_from_party(self.claimant,
            at_date)

    @fields.depends('claimant', 'declaration_date')
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
        else:
            self.raise_user_error('no_main_contract')

    def get_product(self):
        return self.get_contract().offered


class Loss(model.CoopSQL, model.CoopView):
    'Loss'

    __name__ = 'claim.loss'

    claim = fields.Many2One('claim', 'Claim', ondelete='CASCADE')
    start_date = fields.Date('Loss Date')
    end_date = fields.Date('End Date', states={
            'invisible': Bool(~Eval('with_end_date')),
            'required': Bool(Eval('with_end_date')),
            }, depends=['with_end_date'],)
    loss_desc = fields.Many2One('benefit.loss.description', 'Loss Descriptor',
        ondelete='RESTRICT', domain=[
            If(~~Eval('_parent_claim', {}).get('main_contract'),
                ('id', 'in', Eval('possible_loss_descs')), ())
            ],
        depends=['possible_loss_descs'])
    possible_loss_descs = fields.Function(
        fields.One2Many('benefit.loss.description', None,
            'Possible Loss Descs'),
        'on_change_with_possible_loss_descs')
    event_desc = fields.Many2One('benefit.event.description', 'Event',
        domain=[('loss_descs', '=', Eval('loss_desc'))],
        states={'invisible': Bool(Eval('main_loss'))},
        depends=['loss_desc'], ondelete='RESTRICT')
    services = fields.One2Many(
        'contract.service', 'loss', 'Delivered Services',
        domain=[
            ('contract', 'in',
                Eval('_parent_claim', {}).get('possible_contracts'))
            ],)
    multi_level_view = fields.One2Many('contract.service',
        'loss', 'Delivered Services')
    main_loss = fields.Many2One('claim.loss', 'Main Loss',
        domain=[('claim', '=', Eval('claim')), ('id', '!=', Eval('id'))],
        depends=['claim', 'id'], ondelete='CASCADE',
        states={
            'invisible': Eval('_parent_claim', {}).get('reopened_reason')
            != 'relapse'})
    sub_losses = fields.One2Many('claim.loss', 'main_loss', 'Sub Losses')
    with_end_date = fields.Function(
        fields.Boolean('With End Date'),
        'get_with_end_date')
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={'invisible': ~Eval('extra_data')})

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

    @fields.depends('loss_desc', 'extra_data')
    def on_change_with_extra_data(self):
        res = {}
        if self.loss_desc:
            res = utils.init_extra_data(
                self.loss_desc.extra_data_def)
        return res

    def init_from_claim(self, claim):
        pass

    def init_services(self, option, benefits):
        if (not hasattr(self, 'services')
                or not self.services):
            self.services = []
        else:
            self.services = list(self.services)
        for benefit in benefits:
            del_service = None
            for other_del_service in self.services:
                if (other_del_service.benefit == benefit
                        and other_del_service.option == option):
                    del_service = other_del_service
            if del_service:
                continue
            Service = Pool().get('contract.service')
            del_service = Service()
            del_service.option = option
            del_service.init_from_loss(self, benefit)
            self.services.append(del_service)

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
        if self.services:
            for del_serv in self.services:
                res.extend(del_serv.get_claim_sub_status())
            return res
        else:
            return ['instruction']

    @fields.depends('main_loss', 'loss_desc')
    def on_change_main_loss(self):
        # TODO : Add possibility to have compatible loss example a disability
        # after a temporary incapacity
        if self.main_loss and self.main_loss.loss_desc:
            self.loss_desc = self.main_loss.loss_desc
            self.with_end_date = self.main_loss.loss_desc.with_end_date
        else:
            self.loss_desc = None
            self.with_end_date = False

    @fields.depends('event_desc', 'loss_desc', 'with_end_date', 'end_date')
    def on_change_loss_desc(self):
        self.with_end_date = self.get_with_end_date('')
        if (self.loss_desc and self.event_desc
                and self.event_desc not in self.loss_desc.event_descs):
            self.event_desc = None
        self.end_date = self.end_date if self.end_date else None

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
        for del_serv in self.services:
            if del_serv.contract:
                res.append(del_serv.contract)
        return list(set(res))

    @fields.depends('claim')
    def on_change_with_possible_loss_descs(self, name=None):
        res = []
        if not self.claim or not self.claim.main_contract:
            return res
        for benefit in self.claim.main_contract.get_possible_benefits(self):
            res.extend(benefit.loss_descs)
        return [x.id for x in set(res)]

    def get_all_extra_data(self, at_date):
        res = {}
        if getattr(self, 'extra_data', None):
            res = self.extra_data
        return res

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['loss'] = self
        # this date is the one used for finding the good rule,
        # so the rules that was effective when the loss occured
        cur_dict['date'] = self.start_date
        cur_dict['start_date'] = self.start_date
        if self.end_date:
            cur_dict['end_date'] = self.end_date


class DeliveredService:
    __name__ = 'contract.service'

    loss = fields.Many2One('claim.loss', 'Loss', ondelete='CASCADE')
    benefit = fields.Many2One('benefit', 'Benefit', ondelete='RESTRICT',
        domain=[
            If(~~Eval('_parent_loss', {}).get('loss_desc'),
                ('loss_descs', '=', Eval('_parent_loss', {}).get('loss_desc')),
                ())
            ], depends=['loss'])
    indemnifications = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications',
        states={'invisible': ~Eval('indemnifications')})
    multi_level_view = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications')
    extra_data = fields.Dict('extra_data', 'Extra Data',
        states={'invisible': ~Eval('extra_data')})

    @classmethod
    def __setup__(cls):
        super(DeliveredService, cls).__setup__()
        utils.update_domain(cls, 'option',
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
        self.on_change_extra_data()

    def get_covered_data(self):
        # TODO : retrieve the good covered data
        for covered_data in self.option.covered_data:
            return covered_data

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['service'] = self
        self.benefit.init_dict_for_rule_engine(cur_dict)
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
        Indemnification = Pool().get('claim.indemnification')
        indemnification = Indemnification()
        self.indemnifications.append(indemnification)
        indemnification.init_from_service(self)
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
    def calculate_services(cls, instances):
        for instance in instances:
            res, errs = instance.calculate()

    def calculate(self):
        cur_dict = {}
        self.init_dict_for_rule_engine(cur_dict)
        # We first check the eligibility of the benefit
        res, errs = self.benefit.get_result('eligibility', cur_dict)
        self.func_error = None
        if res and not res.eligible:
            self.status = 'not_eligible'
            Error = Pool().get('functional_error')
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
        return res, errs

    def get_rec_name(self, name=None):
        if self.benefit:
            res = self.benefit.get_rec_name(name)
            if self.status:
                res += ' [%s]' % coop_string.translate_value(self, 'status')
            return res
        return super(DeliveredService, self).get_rec_name(name)

    @fields.depends('benefit', 'extra_data', 'loss', 'option', 'is_loan',
        'contract')
    def on_change_extra_data(self):
        args = {'date': self.loss.start_date, 'level': 'service'}
        self.init_dict_for_rule_engine(args)
        self.extra_data = self.benefit.get_result('calculated_extra_datas',
            args)[0]

    def get_extra_data_def(self):
        if self.benefit:
            return self.benefit.extra_data_def

    def get_indemnification_being_calculated(self, cur_dict):
        if not hasattr(self, 'indemnifications'):
            return None
        for indemn in self.indemnifications:
            if (indemn.status == 'calculated'
                    and (not getattr(indemn, 'local_currency', None)
                        or indemn.local_currency == cur_dict['currency'])):
                return indemn

    def get_currency(self):
        if self.option:
            return self.option.get_currency()

    def get_claim_sub_status(self):
        if self.indemnifications:
            return [x.get_claim_sub_status() for x in self.indemnifications]
        elif self.status == 'not_eligible':
            return ['rejected']
        else:
            return ['instruction']

    def get_all_extra_data(self, at_date):
        res = {}
        if getattr(self, 'extra_data', None):
            res = self.extra_data
        res.update(self.get_covered_data().get_all_extra_data(at_date))
        res.update(self.loss.get_all_extra_data(at_date))
        return res


class Indemnification(model.CoopView, model.CoopSQL, ModelCurrency):
    'Indemnification'

    __name__ = 'claim.indemnification'

    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        ondelete='RESTRICT', states={'readonly': Eval('status') == 'paid'})
    customer = fields.Many2One('party.party', 'Customer', ondelete='RESTRICT',
        states={'readonly': Eval('status') == 'paid'})
    service = fields.Many2One('contract.service',
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
    status = fields.Selection([
            ('calculated', 'Calculated'),
            ('validated', 'Validated'),
            ('rejected', 'Rejected'),
            ('paid', 'Paid'),
            ], 'Status', sort=False,
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
        ondelete='RESTRICT', states={
            'invisible': ~Eval('local_currency'),
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid')})
    local_currency_digits = fields.Function(
        fields.Integer('Local Currency Digits', states={'invisible': True}),
        'on_change_with_local_currency_digits')
    details = fields.One2Many('claim.indemnification.detail',
        'indemnification', 'Details',
        states={'readonly': Or(~Eval('manual'), Eval('status') == 'paid')})
    manual = fields.Boolean('Manual Calculation',
        states={'readonly': Eval('status') == 'paid'})

    @classmethod
    def __setup__(cls):
        super(Indemnification, cls).__setup__()
        cls.__rpc__.update({
                'validate_indemnification': RPC(instantiate=0, readonly=False),
                'reject_indemnification': RPC(instantiate=0, readonly=False),
                })
        cls._buttons.update({
                'validate_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'reject_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                })

    def init_from_service(self, service):
        self.status = 'calculated'
        # TODO : To enhance
        self.customer = service.loss.claim.claimant

    def get_kind(self, name=None):
        res = ''
        if not self.service:
            return res
        return self.service.benefit.indemnification_kind

    def get_beneficiary(self, beneficiary_kind, del_service):
        res = None
        if beneficiary_kind == 'subscriber':
            res = del_service.contract.get_policy_owner(
                del_service.loss.start_date)
        return res

    def create_details_from_dict(self, details_dict, del_service, currency):
        Detail = Pool().get('claim.indemnification.detail')
        if not getattr(self, 'details', None):
            self.details = []
        else:
            self.details = list(self.details)
            Detail.delete(self.details)
            self.details[:] = []
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            if key not in details_dict:
                continue
            for detail_dict in details_dict[key]:
                detail = Detail()
                detail.init_from_indemnification(self)
                self.details.append(detail)
                detail.kind = key
                for field_name, value in detail_dict.iteritems():
                    # TODO: Temporary Hack
                    if (field_name == 'beneficiary_kind'
                            and not getattr(self, 'beneficiary', None)):
                        self.beneficiary = self.get_beneficiary(value,
                            del_service)
                    else:
                        setattr(detail, field_name, value)
                if ('start_date' in detail_dict
                        and (not getattr(self, 'start_date', None)
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
        if self.service:
            return self.service.get_currency()

    @fields.depends('local_currency')
    def on_change_with_local_currency_digits(self, name=None):
        if self.local_currency:
            return self.local_currency.digits
        return DEF_CUR_DIG

    def get_rec_name(self, name):
        return u'%s %s [%s]' % (
            coop_string.translate_value(self, 'start_date')
            if self.start_date else '',
            self.currency.amount_as_string(self.amount),
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


class IndemnificationDetail(model.CoopSQL, model.CoopView, ModelCurrency):
    'Indemnification Detail'

    __name__ = 'claim.indemnification.detail'

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
        # If a local currency is used details are stored with the local
        # currency to make only one conversion at the indemnification level
        if self.indemnification:
            if self.indemnification.local_currency:
                return self.indemnification.local_currency
            else:
                return self.indemnification.currency


class ClaimIndemnificationValidateDisplay(model.CoopView):
    'Claim Indemnification Validate Display'

    __name__ = 'claim.indemnification.validate.display'

    selection = fields.Selection([
            ('nothing', 'Nothing'),
            ('validate', 'Validate'),
            ('refuse', 'Refuse'),
            ], 'Selection')
    indemnification_displayer = fields.One2Many(
        'claim.indemnification', '', 'Indemnification',
        states={'readonly': True})
    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification', states={'invisible': True, 'readonly': True})
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
        'claim', 'Claim', states={'readonly': True})
    claim_declaration_date = fields.Date('Claim Declaration Date')


class ClaimIndemnificationValidateSelect(model.CoopView):
    'Claim Indemnification Validate Select'

    __name__ = 'claim.indemnification.validate.select'

    indemnifications = fields.One2Many(
        'claim.indemnification.validate.display', '', 'Indemnifications')
    domain_string = fields.Char('Domain',
        states={'invisible': ~Eval('display_domain')})
    modified = fields.Boolean('Modified', states={'invisible': True})
    global_value = fields.Selection([
            ('nothing', 'Nothing'),
            ('validate', 'Validate'),
            ('refuse', 'Refuse'),
            ], 'Force Value')
    display_domain = fields.Boolean('Display Search')
    search_size = fields.Integer('Search Size',
        states={'invisible': ~Eval('display_domain')})

    @classmethod
    def __setup__(cls):
        super(ClaimIndemnificationValidateSelect, cls).__setup__()
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

    @fields.depends('indemnifications', 'modified', 'apply', 'global_value')
    def on_change_global_value(self):
        for elem in self.indemnifications:
            elem.selection = self.global_value
        self.indemnifications = self.indemnifications

    @classmethod
    def find_indemnifications(cls, domain, search_size):
        Indemnification = Pool().get('claim.indemnification')
        indemnifications = Indemnification.search(
            domain, order=[('start_date', 'ASC')], limit=search_size)
        result = []
        for indemnification in indemnifications:
            claim = indemnification.service.loss.claim
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
                        indemnification.customer.get_rec_name(None)),
                    })
        return {'indemnifications': result, 'modified': False}

    @fields.depends('domain_string', 'indemnifications', 'search_size')
    def on_change_domain_string(self):
        Indemnification = Pool().get('claim.indemnification')
        IndemnificationDisplay = Pool().get(
            'claim.indemnification.validate.display')
        indemnifications = Indemnification.search(
            self.domain_string, order=[('start_date', 'ASC')],
            limit=self.search_size)
        self.modified = False
        for indemnification in indemnifications:
            claim = indemnification.service.loss.claim
            indemnificationDisplay = IndemnificationDisplay(
                    selection='nothing',
                    indemnification=indemnification.id,
                    amount=indemnification.amount,
                    start_date=indemnification.start_date,
                    end_date=indemnification.end_date,
                    indemnification_displayer=[indemnification.id],
                    which_display='indemnification',
                    claim=claim.id,
                    claim_declaration_date=claim.declaration_date,
                    claim_number='%s' % claim.name,
                    covered_element='%s' % (
                        indemnification.customer.get_rec_name(None)))
            self.indemnifications.append(indemnificationDisplay)

    @fields.depends('indemnifications')
    def on_change_with_modified(self):
        if not (hasattr(self, 'indemnifications') and self.indemnifications):
            return
        for indemnification in self.indemnifications:
            if (hasattr(indemnification, 'selection') and
                    indemnification.selection != 'nothing'):
                return True
        return False


class ClaimIndemnificationValidate(Wizard):
    'Claim Indemnification Validate'

    __name__ = 'claim.indemnification.validate'

    start_state = 'select_indemnifications'
    select_indemnifications = StateView(
        'claim.indemnification.validate.select',
        'claim.indemnification_validate_select_form', [
            Button('Quit', 'end', 'tryton-cancel'),
            Button('Continue', 'reload_selection', 'tryton-refresh')])
    reload_selection = StateTransition()

    def default_select_indemnifications(self, fields):
        today = utils.today()
        default_max_date = datetime.date(today.year, today.month, 1)
        domain_string = 'status: = calculated, start_date: <= %s' % (
            coop_date.get_end_of_period(default_max_date, 'month'))
        Selector = Pool().get('claim.indemnification.validate.select')
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
        Claim = Pool().get('claim')
        Indemnification = Pool().get('claim.indemnification')
        Indemnification.validate_indemnification(
            Indemnification.browse(to_validate))
        Indemnification.reject_indemnification(
            Indemnification.browse(to_reject))
        for claim in Claim.browse(claims):
            claim.complete_indemnifications()
            Claim.write([claim], {})
        Selector = Pool().get('claim.indemnification.validate.select')
        self.select_indemnifications.indemnifications = \
            Selector.find_indemnifications(
                Selector.build_domain(
                    self.select_indemnifications.domain_string),
                self.select_indemnifications.search_size)['indemnifications']
        return 'select_indemnifications'
