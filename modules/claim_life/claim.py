# -*- coding:utf-8 -*-
from decimal import Decimal
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool, Or
from trytond.wizard import Wizard, StateView, StateTransition, Button
from trytond.rpc import RPC

from trytond.modules.cog_utils import fields, model, coop_string, coop_date, \
    utils
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.benefit.benefit import INDEMNIFICATION_DETAIL_KIND
from trytond.modules.benefit.benefit import INDEMNIFICATION_KIND
from trytond.modules.currency_cog.currency import DEF_CUR_DIG

__metaclass__ = PoolMeta
__all__ = [
    'Loss',
    'Claim',
    'ClaimService',
    'Indemnification',
    'IndemnificationDetail',
    'ClaimIndemnificationValidateDisplay',
    'ClaimIndemnificationValidateSelect',
    'ClaimIndemnificationValidate',
    ]


class Loss:
    __name__ = 'claim.loss'

    end_date = fields.Date('End Date', states={
            'invisible': Bool(~Eval('with_end_date')),
            'required': Bool(Eval('with_end_date')),
            }, depends=['with_end_date'],)
    possible_covered_persons = fields.Function(
        fields.One2Many('party.party', None, 'Covered Persons',
            states={'invisible': True}),
        'on_change_with_possible_covered_persons')
    covered_person = fields.Many2One('party.party', 'Covered Person',
        # TODO: Temporary hack, the function field is not calculated
        # when storing the object
        domain=[If(
                Bool(Eval('possible_covered_persons')),
                ('id', 'in', Eval('possible_covered_persons')),
                ()
                )
            ], ondelete='RESTRICT', depends=['possible_covered_persons'])
    with_end_date = fields.Function(
        fields.Boolean('With End Date'), 'get_with_end_date')

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls._error_messages.update({
                'end_date_smaller_than_start_date':
                'End Date is smaller than start date',
                })

    @classmethod
    def validate(cls, instances):
        super(Loss, cls).validate(instances)
        for instance in instances:
            instance.check_end_date()

    def check_end_date(self):
        if (self.start_date and self.end_date
                and self.end_date < self.start_date):
            self.raise_user_error('end_date_smaller_than_start_date')

    def get_possible_covered_persons(self):
        res = []
        CoveredElement = Pool().get('contract.covered_element')
        if not self.claim:
            return []
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.claim.claimant, self.start_date):
            res.extend(covered_element.get_covered_parties(self.start_date))
        return res

    @fields.depends('claim', 'start_date')
    def on_change_with_possible_covered_persons(self, name=None):
        return [x.id for x in self.get_possible_covered_persons()]

    @fields.depends('covered_person', 'possible_loss_descs', 'claim',
        'start_date', 'loss_desc', 'event_desc')
    def on_change_covered_person(self):
        self.possible_loss_descs = self.on_change_with_possible_loss_descs()

    @fields.depends('event_desc', 'loss_desc', 'with_end_date', 'end_date')
    def on_change_loss_desc(self):
        self.with_end_date = self.get_with_end_date('')
        if (self.loss_desc and self.event_desc
                and self.event_desc not in self.loss_desc.event_descs):
            self.event_desc = None
        self.end_date = self.end_date if self.end_date else None

    def get_rec_name(self, name=None):
        res = ''
        if self.loss_desc:
            res = self.loss_desc.rec_name
        if self.start_date and not self.end_date:
            res += ' [%s]' % self.start_date
        elif self.start_date and self.end_date:
            res += ' [%s - %s]' % (self.start_date, self.end_date)
        return res or super(Loss, self).get_rec_name(name)

    def get_with_end_date(self, name=None):
        return self.loss_desc and self.loss_desc.with_end_date

    @classmethod
    def add_func_key(cls, values):
        # Update without func_key is not handled for now
        values['_func_key'] = None

    @property
    def date(self):
        return self.start_date

    def init_dict_for_rule_engine(self, cur_dict):
        super(Loss, self).init_dict_for_rule_engine(cur_dict)
        if self.loss_desc.loss_kind == 'life':
            if self.end_date and 'end_date' not in cur_dict:
                cur_dict['end_date'] = self.end_date

    def get_covered_person(self):
        if hasattr(self, 'loss_desc') and self.loss_desc and hasattr(
                self, 'covered_person'):
            if self.loss_desc.loss_kind == 'life':
                return self.covered_person


class Claim:
    'Claim'
    __name__ = 'claim'

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


class ClaimService:
    __name__ = 'claim.service'

    indemnifications = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications',
        states={'invisible': ~Eval('indemnifications')}, delete_missing=True)
    multi_level_view = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications', delete_missing=True)

    @classmethod
    def _export_skips(cls):
        return super(ClaimService, cls)._export_skips() | {'multi_level_view'}

    def calculate(self):
        if self.loss.loss_desc.loss_kind == 'life':
            cur_dict = {}
            self.init_dict_for_rule_engine(cur_dict)
            cur_dict['currency'] = self.get_currency()
            self.create_indemnification(cur_dict)
        else:
            return super(ClaimService, self).calculate()

    def get_claim_sub_status(self):
        if self.indemnifications:
            return [x.get_claim_sub_status() for x in self.indemnifications]
        return super(ClaimService, self).get_claim_sub_status()

    def get_covered_person(self):
        if self.loss.loss_desc.loss_kind == 'life':
            return self.loss.covered_person
        return super(ClaimService, self).get_covered_person()

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(
            cur_dict)
        if self.loss.loss_desc.loss_kind == 'life':
            cur_dict['covered_person'] = self.get_covered_person()

    def create_indemnification_details(self, cur_dict):
        IndemnificationDetail = Pool().get('claim.indemnification.detail')
        details_dict, _ = self.benefit.get_result('indemnification', cur_dict)
        return IndemnificationDetail.create_details_from_dict(details_dict,
            cur_dict['currency'])

    def create_indemnification(self, cur_dict):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')

        indemnifications = list(getattr(self, 'indemnifications', []))
        indemnifications = [x for x in indemnifications
            if x.status != 'calculated']

        indemnification = Indemnification()
        indemnification.init_from_service(self)
        details = self.create_indemnification_details(cur_dict)

        if 'end_date' in cur_dict:
            while details[-1].end_date < cur_dict['end_date']:
                cur_dict = cur_dict.copy()
                cur_dict['date'] = coop_date.add_day(
                    details[-1].end_date, 1)
                details += self.create_indemnification_details(cur_dict)
        indemnification.start_date = details[0].start_date
        indemnification.details = details
        indemnification.calculate_amount_and_end_date_from_details(self,
            cur_dict['currency'])
        indemnifications.append(indemnification)
        self.indemnifications = indemnifications
        return True, []

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

    def get_indemnification_being_calculated(self, cur_dict):
        if not hasattr(self, 'indemnifications'):
            return None
        for indemn in self.indemnifications:
            if (indemn.status == 'calculated'
                    and (not getattr(indemn, 'local_currency', None)
                        or indemn.local_currency == cur_dict['currency'])):
                return indemn


class Indemnification(model.CoopView, model.CoopSQL, ModelCurrency):
    'Indemnification'

    __name__ = 'claim.indemnification'

    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        ondelete='RESTRICT', states={'readonly': Eval('status') == 'paid'},
        depends=['status'])
    customer = fields.Many2One('party.party', 'Customer', ondelete='RESTRICT',
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
    service = fields.Many2One('claim.service', 'Claim Service',
        ondelete='CASCADE', select=True, required=True,
        states={'readonly': Eval('status') == 'paid'})
    kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Kind', sort=False,
            states={'invisible': True}),
        'get_kind')
    kind_string = kind.translated('kind')
    start_date = fields.Date('Start Date', states={
            'invisible': Eval('kind') != 'period',
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            }, depends=['manual', 'status'])
    end_date = fields.Date('End Date', states={
            'invisible': Eval('kind') != 'period',
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            }, depends=['manual', 'status'])
    status = fields.Selection([
            ('calculated', 'Calculated'),
            ('validated', 'Validated'),
            ('rejected', 'Rejected'),
            ('paid', 'Paid'),
            ], 'Status', sort=False,
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
    status_string = status.translated('status')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits', 'status', 'manual'],
        states={'readonly': Or(~Eval('manual'), Eval('status') == 'paid')})
    local_currency_amount = fields.Numeric('Local Currency Amount',
        digits=(16, Eval('local_currency_digits', DEF_CUR_DIG)),
        states={
            'invisible': ~Eval('local_currency'),
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['local_currency_digits', 'status', 'manual'])
    local_currency = fields.Many2One('currency.currency', 'Local Currency',
        ondelete='RESTRICT', states={
            'invisible': ~Eval('local_currency'),
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['status', 'manual'])
    local_currency_digits = fields.Function(
        fields.Integer('Local Currency Digits', states={'invisible': True}),
        'on_change_with_local_currency_digits')
    details = fields.One2Many('claim.indemnification.detail',
        'indemnification', 'Details',
        states={'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['status', 'manual'], delete_missing=True)
    manual = fields.Boolean('Manual Calculation',
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])

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
        self.beneficiary = self.get_beneficiary(
            service.benefit.beneficiary_kind, service)

    def get_beneficiary(self, beneficiary_kind, del_service):
        if beneficiary_kind == 'covered_person':
            res = del_service.loss.covered_person
        if beneficiary_kind == 'subscriber':
            res = del_service.contract.get_policy_owner(
                del_service.loss.start_date)
        return res

    def get_kind(self, name=None):
        res = ''
        if not self.service:
            return res
        return self.service.benefit.indemnification_kind

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
        'Indemnification', ondelete='CASCADE', required=True, select=True)
    start_date = fields.Date('Start Date', states={
            'invisible':
            Eval('_parent_indemnification', {}).get('kind') != 'period'
            })
    end_date = fields.Date('End Date', states={
            'invisible':
            Eval('_parent_indemnification', {}).get('kind') != 'period'
            })
    kind = fields.Selection(INDEMNIFICATION_DETAIL_KIND, 'Kind', sort=False)
    kind_string = kind.translated('kind')
    amount_per_unit = fields.Numeric('Amount per Unit')
    nb_of_unit = fields.Numeric('Nb of Unit')
    unit = fields.Selection(coop_date.DAILY_DURATION, 'Unit')
    unit_string = unit.translated('unit')
    amount = fields.Numeric('Amount')

    def calculate_amount(self):
        self.amount = self.amount_per_unit * self.nb_of_unit

    def get_currency(self):
        # If a local currency is used details are stored with the local
        # currency to make only one conversion at the indemnification level
        if self.indemnification.local_currency:
            return self.indemnification.local_currency
        else:
            return self.indemnification.currency

    @classmethod
    def create_details_from_dict(cls, details_dict, currency):
        details = []
        for key, fancy_name in INDEMNIFICATION_DETAIL_KIND:
            if key not in details_dict:
                continue
            for detail_dict in details_dict[key]:
                detail = cls(**detail_dict)
                details.append(detail)
                detail.kind = key
        return details


class ClaimIndemnificationValidateDisplay(model.CoopView):
    'Claim Indemnification Validate Display'

    __name__ = 'claim.indemnification.validate.display'

    selection = fields.Selection([
            ('nothing', 'Nothing'),
            ('validate', 'Validate'),
            ('refuse', 'Refuse'),
            ], 'Selection')
    selection_string = selection.translated('selection')
    indemnification_displayer = fields.One2Many(
        'claim.indemnification', '', 'Indemnification',
        states={'readonly': True})
    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification', states={'invisible': True, 'readonly': True},
        ondelete='SET NULL')
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
        'claim', 'Claim', states={'readonly': True}, ondelete='SET NULL')
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
    global_value_string = global_value.translated('global_value')
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

    @fields.depends('indemnifications', 'modified', 'global_value')
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
            self.indemnifications = self.indemnifications + (
                indemnificationDisplay,)

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
        'claim_life.indemnification_validate_select_form', [
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
        pool = Pool()
        Claim = pool.get('claim')
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
        Indemnification = Pool().get('claim.indemnification')
        Indemnification.validate_indemnification(
            Indemnification.browse(to_validate))
        Indemnification.reject_indemnification(
            Indemnification.browse(to_reject))
        for claim in Claim.browse(claims):
            claim.complete_indemnifications()
        Claim.save(claims)
        Selector = Pool().get('claim.indemnification.validate.select')
        self.select_indemnifications.indemnifications = \
            Selector.find_indemnifications(
                Selector.build_domain(
                    self.select_indemnifications.domain_string),
                self.select_indemnifications.search_size)['indemnifications']
        return 'select_indemnifications'
