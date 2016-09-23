# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or, Bool, In, Not
from trytond.model import ModelView
from trytond.rpc import RPC

from trytond.modules.cog_utils import fields, model, coop_string, utils, \
    coop_date
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.claim_indemnification.benefit import \
    INDEMNIFICATION_DETAIL_KIND
from trytond.modules.claim_indemnification.benefit import INDEMNIFICATION_KIND
from trytond.modules.currency_cog.currency import DEF_CUR_DIG
from trytond.modules.rule_engine import get_rule_mixin

__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    'Loss',
    'ClaimService',
    'Indemnification',
    'IndemnificationTaxes',
    'IndemnificationDetail',
    'IndemnificationControlRule'
    ]


PERIOD_FREQUENCIES = [
    ('quarterly', 'Quarterly'),
    ('monthly', 'Monthly'),
    ]


class Claim:
    __name__ = 'claim'
    invoices = fields.Function(
        fields.One2Many('account.invoice', None, 'Invoices'),
        'get_invoices')
    indemnifications_details = fields.Function(
        fields.One2Many('claim.indemnification.detail', None,
            'Indemnifications Details'),
        'get_indemnifications_details')
    is_services_deductible = fields.Function(fields.Boolean(
            'Is Services Deductible'),
        'get_is_services_deductible')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._buttons.update({
                'button_calculate': {
                    'invisible': Eval('status').in_(['closed']),
                    },
                'create_indemnification': {
                    'invisible': Eval('status').in_(['closed']),
                    },
                'schedule_all': {
                    'invisible': Eval('status').in_(['closed']),
                    },
                })

    def get_is_services_deductible(self, name=None):
        return (self.indemnifications_details and all([x.kind == 'deductible'
                    for x in self.indemnifications_details]))

    def get_indemnifications_details(self, name):
        IndemnificationDetail = Pool().get('claim.indemnification.detail')
        return [i.id for i in IndemnificationDetail.search(
                [('indemnification.service.claim', '=', self.id)])]

    def calculate(self):
        for loss in self.losses:
            for service in loss.services:
                if service.status == 'calculating':
                    service.calculate()
            loss.services = loss.services
        self.losses = self.losses

    @classmethod
    @ModelView.button
    def button_calculate(cls, claims):
        for claim in claims:
            claim.calculate()
        cls.save(claims)

    def get_invoices(self, name):
        pool = Pool()
        Detail = pool.get('account.invoice.line.claim_detail')
        details = Detail.search([('claim', '=', self.id)])
        invoices = [detail.invoice_line.invoice for detail in details]
        invoices = list(set(invoices))
        return [invoice.id for invoice in invoices]

    def complete_indemnifications(self):
        Service = Pool().get('claim.service')
        res = True, []
        to_save = []
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
                    to_save.append(service)
        Service.save(to_save)
        return res

    @classmethod
    @ModelView.button_action(
        'claim_indemnification.act_create_claim_indemnification_wizard')
    def create_indemnification(cls, services):
        pass

    @classmethod
    @ModelView.button
    def schedule_all(cls, claims):
        if not claims:
            return
        Indemnification = Pool().get('claim.indemnification')
        Indemnification.schedule(claims[0].indemnifications_to_schedule)


class Loss:
    __name__ = 'claim.loss'

    def close(self, sub_status, date=None):
        super(Loss, self).close(sub_status, date)
        max_end_date = datetime.date.min
        if self.with_end_date and not self.end_date:
            for service in self.services:
                for indemnification in service.indemnifications:
                    max_end_date = max(indemnification.end_date, max_end_date)
            if max_end_date != datetime.date.min:
                self.end_date = max_end_date
                self.save()


class ClaimService:
    __name__ = 'claim.service'

    indemnifications = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications', delete_missing=True)
    multi_level_view = fields.One2Many('claim.indemnification',
        'service', 'Indemnifications', delete_missing=True)
    paid_until_date = fields.Function(fields.Date('Paid Until Date',
            readonly=True,
            states={'invisible': ~(Bool(Eval(
                            'has_automatic_period_calculation')))},
            depends=['has_automatic_period_calculation']),
        getter='get_paid_until_date')
    has_automatic_period_calculation = fields.Function(
        fields.Boolean('has_automatic_period_calculation'),
        getter='getter_has_automatic_period_calculation')
    payment_accepted_until_date = fields.Date('Payments Accepted Until:',
          states={'invisible': ~(Bool(Eval(
                    'has_automatic_period_calculation')))},
          depends=['has_automatic_period_calculation'])
    period_frequency = fields.Selection(PERIOD_FREQUENCIES, 'Period Frequency',
          states={'invisible': ~(Bool(Eval(
                        'has_automatic_period_calculation')))},
          depends=['has_automatic_period_calculation'])
    deductible_end_date = fields.Function(
        fields.Date('Deductible End Date'),
        'get_deductible_end_date')

    @classmethod
    def __setup__(cls):
        super(ClaimService, cls).__setup__()
        cls.__rpc__.update({
                'create_indemnification': RPC(instantiate=0,
                    readonly=False),
                'fill_extra_datas': RPC(instantiate=0,
                    readonly=False),
                })
        cls._error_messages.update({
            'overlap_date': 'Are you sure you want to cancel '
            'the periods between %s and %s?',
            'offset_date': 'The date is not equal to the cancelled date'
            })

    @classmethod
    def _export_skips(cls):
        return super(ClaimService, cls)._export_skips() | {'multi_level_view'}

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(cur_dict)
        cur_dict['date'] = self.loss.start_date
        cur_dict['deductible_end_date'] = self.get_deductible_end_date(
            args=cur_dict)

    def calculate(self):
        cur_dict = {}
        self.init_dict_for_rule_engine(cur_dict)
        cur_dict['currency'] = self.get_currency()
        self.func_error = None
        self.status = 'calculated'
        self.create_indemnification(cur_dict)

    @classmethod
    def calculate_services(cls, instances):
        for instance in instances:
            res, errs = instance.calculate()

    def getter_has_automatic_period_calculation(self, name):
        return self.benefit.has_automatic_period_calculation() \
            if self.benefit else False

    @classmethod
    def default_period_frequency(cls):
        return 'quarterly'

    def get_deductible_end_date(self, name=None, args=None):
        if not args:
            args = {}
            self.init_dict_for_rule_engine(args)
        return self.benefit.calculate_deductible(args)

    def is_deductible(self):
        details = [x for indemn in self.indemnifications for x
            in indemn.details]
        if not details and self.loss.end_date:
            return self.loss.end_date < self.get_deductible_end_date()
        if not self.loss.end_date:
            return False
        return all([x.kind == 'deductible' for x in details])

    def init_from_loss(self, loss, benefit):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        super(ClaimService, self).init_from_loss(loss, benefit)
        self.indemnifications = []
        if self.loss.start_date and self.loss.end_date:
            if self.loss.end_date < self.get_deductible_end_date():
                indemnification = Indemnification(
                    start_date=self.loss.start_date,
                    end_date=self.loss.end_date
                    )
                indemnification.init_from_service(self)
                Indemnification.calculate([indemnification])
                self.indemnifications = [indemnification]

    def get_paid_until_date(self, name):
        cur_date = None
        for indemnification in self.indemnifications:
            if not cur_date:
                cur_date = indemnification.end_date
            else:
                cur_date = max(cur_date, indemnification.end_date)
        return cur_date

    def regularize_indemnification(self, indemnification, details_dict,
            currency):
        amount = sum([x.amount for x in self.indemnifications
            if x.status == 'paid' and x.currency == currency])
        if amount:
            details_dict['regularisation'] = [
                {
                    'amount_per_unit': amount,
                    'nb_of_unit': -1,
                }]

    @classmethod
    def cancel_indemnification(cls, services, at_date):
        to_cancel = []
        to_delete = []
        ClaimIndemnification = Pool().get('claim.indemnification')
        for service in services:
            for indemn in service.indemnifications:
                if (indemn.status != 'cancelled' and
                        indemn.status != 'cancel_paid'):
                    if at_date < indemn.end_date:
                        if indemn.status == 'paid':
                            to_cancel.append(indemn)
                        else:
                            to_delete.append(indemn)
        if to_cancel:
            if at_date != to_cancel[0].start_date:
                cls.raise_user_error('offset_date')
            cls.raise_user_warning('overlap_date', 'overlap_date',
                (to_cancel[0].start_date, to_cancel[-1].end_date))
            ClaimIndemnification.cancel_indemnification(to_cancel)
        if to_delete:
            ClaimIndemnification.delete(to_delete)
        return to_cancel

    @classmethod
    @ModelView.button_action(
        'claim_indemnification.act_create_indemnification_wizard')
    def create_indemnification(cls, services):
        pass

    @classmethod
    @ModelView.button_action(
        'claim_indemnification.act_fill_extra_data_wizard')
    def fill_extra_datas(cls, services):
        pass


class Indemnification(model.CoopView, model.CoopSQL, ModelCurrency):
    'Indemnification'

    __name__ = 'claim.indemnification'

    beneficiary = fields.Many2One('party.party', 'Beneficiary',
        ondelete='RESTRICT', states={'readonly': Eval('status') == 'paid'},
        depends=['status'])
    service = fields.Many2One('claim.service', 'Claim Service',
        ondelete='CASCADE', select=True, required=True,
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
    kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Kind', sort=False),
        'get_kind')
    kind_string = kind.translated('kind')
    start_date = fields.Date('Start Date', states={
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            }, depends=['manual', 'status', 'kind'], required=True)
    end_date = fields.Date('End Date', states={
            'readonly': Or(~Eval('manual'), Eval('status') == 'paid'),
            }, depends=['manual', 'status', 'kind'])
    status = fields.Selection([
            ('calculated', 'Calculated'),
            ('scheduled', 'Scheduled'),
            ('controlled', 'Controlled'),
            ('validated', 'Validated'),
            ('rejected', 'Rejected'),
            ('paid', 'Paid'),
            ('cancelled', 'Annule'),
            ('cancel_paid', 'Paid & Cancelled'),
            ('cancel_scheduled', 'Schedule Cancelled'),
            ('cancel_validated', 'Validate Cancelled'),
            ('cancel_controlled', 'Control Cancelled'),
            ], 'Status', sort=False,
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
    status_string = status.translated('status')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        states={'readonly': Or(~Eval('manual'), Eval('status') == 'paid')},
        depends=['currency_digits', 'status', 'manual'])
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
    taxes = fields.Many2Many('claim.indemnification-acount.tax',
        'indemnification', 'tax', 'Taxes')
    benefit_description = fields.Function(
        fields.Char('Prestation'),
        'get_benefit_description')
    control_reason = fields.Char('Control Reason')
    payback_method = fields.Selection([
            ('continuous', 'Continuous'),
            ('immediate', 'Immediate'),
            ('planned', 'Planned'),
            ('', ''),
            ], 'Repayment Method', states={
                'invisible': Not(In(Eval('status'),
                        ['cancelled', 'cancel_paid'])),
                'readonly': Eval('status') == 'cancel_paid'
            })
    payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Payment Term', states={
            'invisible': Not(In(Eval('status'),
                    ['cancelled', 'cancel_paid'])),
            'readonly': Eval('status') == 'cancel_paid'
            })

    @classmethod
    def __setup__(cls):
        super(Indemnification, cls).__setup__()
        cls.__rpc__.update({
                'validate_indemnification': RPC(instantiate=0, readonly=False),
                'reject_indemnification': RPC(instantiate=0, readonly=False),
                })
        cls._buttons.update({
                'calculate': {
                    'invisible': Eval('status') != 'calculated'},
                'validate_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'reject_indemnification': {
                    'invisible': Eval('status') != 'calculated'},
                'cancel_indemnification': {
                    'invisible': Eval('status') != 'paid'},
                'schedule': {
                    'invisible': Eval('status') != 'calculated'},
                })
        cls._error_messages.update({
                'bad_dates': 'The indemnification period (%(indemn_start)s - '
                "%(indemn_end)s) is not compatible with the contract's end "
                'date (%(contract_end)s).',
                })

    def get_benefit_description(self, name):
        if self.service and self.service.benefit:
            return self.service.benefit.rec_name
        return ''

    def init_from_service(self, service):
        self.status = 'calculated'
        self.service = service
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
        if self.service:
            return self.service.benefit.indemnification_kind
        return ''

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

    def require_control(self):
        pool = Pool()
        ClaimConfiguration = pool.get('claim.configuration')
        config = ClaimConfiguration.get_singleton()
        ctx = {}
        self.init_dict_for_rule_engine(ctx)
        ctx['date'] = self.start_date
        if not config.control_rule:
            return False, ''
        return config.control_rule.calculate_rule(ctx)

    def init_dict_for_rule_engine(self, cur_dict):
        self.service.init_dict_for_rule_engine(cur_dict)
        cur_dict['indemnification'] = self

    @fields.depends('local_currency')
    def on_change_with_local_currency_digits(self, name=None):
        if self.local_currency:
            return self.local_currency.digits
        return DEF_CUR_DIG

    def get_rec_name(self, name):
        return u'%s - %s: %s [%s]' % (
            coop_string.translate_value(self, 'start_date')
            if self.start_date else '',
            coop_string.translate_value(self, 'end_date')
            if self.end_date else '',
            self.get_currency().amount_as_string(self.amount)
            if self.amount else '',
            coop_string.translate_value(self, 'status') if self.status else '',
            )

    def complete_indemnification(self):
        if self.status == 'validated' and self.amount:
            self.invoice([self])
        return True, []

    def is_pending(self):
        return self.amount > 0 and self.status not in ['paid', 'rejected']

    @classmethod
    def check_schedulability(cls, indemnifications):
        pass

    @classmethod
    @ModelView.button
    def schedule(cls, indemnifications):
        Event = Pool().get('event')
        schedule = []
        schedule_cancel = []
        control = []
        control_cancel = []
        with model.error_manager():
            cls.check_schedulability(indemnifications)
        for indemnification in indemnifications:
            do_control, reason = indemnification.require_control()
            if do_control is True:
                if indemnification.status == 'cancelled':
                    schedule_cancel.append(indemnification)
                else:
                    schedule.append(indemnification)
            else:
                if indemnification.status == 'cancelled':
                    control_cancel.append(indemnification)
                else:
                    control.append(indemnification)
        cls.write(
            schedule, {
                'status': 'scheduled', 'control_reason': reason
                },
            schedule_cancel, {
                'status': 'cancel_scheduled', 'control_reason': reason
                },
            control, {'status': 'controlled'},
            control_cancel, {'status': 'cancel_controlled'})
        Event.notify_events(indemnifications, 'schedule_indemnification')

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
    @ModelView.button
    def calculate(cls, indemnifications):
        pool = Pool()
        IndemnificationDetail = pool.get('claim.indemnification.detail')
        Indemnification = pool.get('claim.indemnification')
        with model.error_manager():
            cls.check_calculable(indemnifications)
        to_save = []
        for indemnification in indemnifications:
            cur_dict = {}
            indemnification.service.init_dict_for_rule_engine(cur_dict)
            cur_dict['indemnification'] = indemnification
            cur_dict['date'] = cur_dict['loss'].start_date
            cur_dict['start_date'] = indemnification.start_date
            cur_dict['end_date'] = indemnification.end_date
            cur_dict['currency'] = indemnification.service.get_currency()
            details = indemnification.service.benefit.calculate_benefit(
                cur_dict)
            details = [IndemnificationDetail(**detail) for detail in details]
            indemnification.details = details
            indemnification.amount = sum([getattr(d, 'amount', 0)
                    for d in details])
            to_save.append(indemnification)
        Indemnification.save(to_save)

    @classmethod
    def check_calculable(cls, indemnifications):
        for indemnification in indemnifications:
            if not indemnification.service:
                continue
            contract = indemnification.service.contract
            if not contract or contract.status != 'terminated':
                continue
            if (contract.post_termination_claim_behaviour !=
                    'stop_indemnisations'):
                continue
            if (contract.end_date > indemnification.start_date or
                    contract.end_date > indemnification.end_date):
                cls.append_functional_error('bad_dates', {
                        'indemn_start': indemnification.start_date,
                        'indemn_end': indemnification.end_date,
                        'contract_end': contract.end_date})

    @classmethod
    @ModelView.button
    def validate_indemnification(cls, indemnifications):
        validate = []
        cancelled = []
        for indemn in indemnifications:
            if indemn.status == 'cancelled':
                cancelled.append(indemn)
            else:
                validate.append(indemn)
        cls.write(
            validate, {'status': 'validated'},
            cancelled, {'status': 'cancel_validated'})
        Event = Pool().get('event')
        Event.notify_events(indemnifications, 'validate_indemnification')

    @classmethod
    def reject_indemnification(cls, indemnifications):
        cls.write(indemnifications, {'status': 'rejected'})
        Event = Pool().get('event')
        Event.notify_events(indemnifications, 'reject_indemnification')

    @classmethod
    @ModelView.button
    def cancel_indemnification(cls, indemnifications):
        pool = Pool()
        cls.write(indemnifications, {'status': 'cancelled'})
        Event = pool.get('event')
        Event.notify_events(indemnifications, 'cancel_indemnification')

    @classmethod
    def control_indemnification(cls, indemnifications):
        control = []
        cancelled = []
        for indemn in indemnifications:
            if indemn.status == 'cancelled':
                cancelled.append(indemn)
            else:
                control.append(indemn)
        cls.write(control, {'status': 'controlled'},
                  cancelled, {'status': 'cancel_controlled'})

    @classmethod
    def get_journal(cls):
        pool = Pool()
        Journal = pool.get('account.journal')

        journals = Journal.search([
                ('type', '=', 'claim'),
                ], limit=1)
        if journals:
            return journals[0]

    @classmethod
    def _get_invoice(cls, key):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        PaymentTerm = pool.get('account.invoice.payment_term')
        party = key['party']
        if 'payment_term' in key:
            payment_term = key['payment_term']
        elif party.supplier_payment_term:
            payment_term = party.supplier_payment_term
        else:
            payment_term = PaymentTerm.search([])[0]
        return Invoice(
            company=key['company'],
            type='in',
            journal=cls.get_journal(),
            party=party,
            invoice_address=party.address_get(type='invoice'),
            currency=key['currency'],
            account=party.account_payable,
            payment_term=payment_term,
            invoice_date=utils.today(),
            currency_date=utils.today(),
            description='%s - %s' % (
                key['indemnification'].service.loss.loss_desc.name,
                key['indemnification'].service.loss.claim.claimant.full_name)
                )

    @classmethod
    def _get_invoice_line(cls, key, invoice, indemnification):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        LineDetail = pool.get('account.invoice.line.claim_detail')
        invoice_line = InvoiceLine()
        invoice_line.invoice = invoice
        invoice_line.type = 'line'
        invoice_line.product = key['product']
        invoice_line.quantity = 1
        invoice_line.on_change_product()
        invoice_line.unit_price = indemnification.amount
        if indemnification.status == 'cancel_validated':
            invoice_line.unit_price = -invoice_line.unit_price
        detail = LineDetail()
        detail.service = indemnification.service
        detail.indemnification = indemnification
        detail.claim = indemnification.service.loss.claim
        invoice_line.claim_details = [detail]
        return invoice_line

    @classmethod
    def add_taxes_to_invoice(cls, invoice, taxes, amount):
        pool = Pool()
        Tax = pool.get('account.tax')
        InvoiceLine = pool.get('account.invoice.line')
        to_pay = Tax.reverse_compute(amount, taxes)
        to_pay = to_pay.quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])
        tax_details = Tax.compute(taxes, amount, 1)
        for tax in tax_details:
            invoice_line = InvoiceLine()
            invoice_line.description = tax['tax'].name
            invoice_line.invoice = invoice
            invoice_line.type = 'line'
            invoice_line.account = tax['tax'].invoice_account
            invoice_line.quantity = 1
            invoice_line.on_change_product()
            invoice_line.unit_price = -tax['amount'].quantize(
                Decimal(1) / 10 ** InvoiceLine.unit_price.digits[1])
            invoice.lines = list(invoice.lines) + [invoice_line]

    @classmethod
    def invoice(cls, indemnifications):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoices = []
        paid = []
        cancelled = []
        for indemnification in indemnifications:
            key = {
                'party': indemnification.beneficiary,
                'product': indemnification.service.benefit.account_product,
                'company': indemnification.service.contract.company,
                'currency': indemnification.currency,
                'indemnification': indemnification,
                }
            if indemnification.status == 'cancel_validated':
                cancelled.append(indemnification)
                if indemnification.payback_method == 'immediate':
                    # do something special here, discuss with Fred
                    pass
                elif indemnification.payback_method == 'planned':
                    key.update({'payment_term': indemnification.payment_term})
            else:
                paid.append(indemnification)
            invoice = cls._get_invoice(key)
            invoice.lines = [cls._get_invoice_line(key, invoice,
                    indemnification)]
            if indemnification.taxes:
                cls.add_taxes_to_invoice(invoice, indemnification.taxes,
                    indemnification.amount)
            invoices.append(invoice)
        Invoice.save(invoices)
        Invoice.post(invoices)
        cls.write(paid, {'status': 'paid'},
            cancelled, {'status': 'cancel_paid'})


class IndemnificationTaxes(model.CoopSQL):
    'Indemnification - Taxes Relation'

    __name__ = 'claim.indemnification-acount.tax'

    tax = fields.Many2One('account.tax', 'Tax', ondelete='CASCADE',
        required=True)
    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification', ondelete='RESTRICT', required=True, select=True)


class IndemnificationDetail(model.CoopSQL, model.CoopView, ModelCurrency):
    'Indemnification Detail'

    __name__ = 'claim.indemnification.detail'

    indemnification = fields.Many2One('claim.indemnification',
        'Indemnification', ondelete='CASCADE', required=True, select=True)
    start_date = fields.Date('Start Date',
        states={'invisible': Eval('indemnification_kind') != 'period'},
        depends=['indemnification_kind'])
    end_date = fields.Date('End Date',
        states={'invisible': Eval('indemnification_kind') != 'period'},
        depends=['indemnification_kind'])
    indemnification_kind = fields.Function(
        fields.Selection(INDEMNIFICATION_KIND, 'Indemnification Kind',
            sort=False),
        'get_indemnification_kind')
    kind = fields.Selection(INDEMNIFICATION_DETAIL_KIND, 'Kind', sort=False)
    kind_string = kind.translated('kind')
    amount_per_unit = fields.Numeric('Amount per Unit',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])
    nb_of_unit = fields.Numeric('Nb of Unit')
    unit = fields.Selection(coop_date.DAILY_DURATION, 'Unit')
    unit_string = unit.translated('unit')
    amount = fields.Numeric('Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])
    description = fields.Text('Description')
    duration_description = fields.Function(
        fields.Char('Duration'),
        'get_duration_description')
    status = fields.Function(
        fields.Char('Status'), 'get_status_string')
    base_amount = fields.Numeric('Base Amount',
        digits=(16, Eval('currency_digits', DEF_CUR_DIG)),
        depends=['currency_digits'])

    def get_indemnification_kind(self, name):
        return self.indemnification.kind

    def get_duration_description(self, name):
        return '%s %s(s)' % (self.nb_of_unit, self.unit_string)

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

    def get_status_string(self, name):
        if self.indemnification.status == 'cancelled':
            return '%s - [%s]' % (
                self.kind_string, self.indemnification.status_string)
        return self.kind_string


class IndemnificationControlRule(
        get_rule_mixin('rule', 'Rule Engine', extra_string='Rule Extra Data'),
        model.CoopSQL, model.CoopView):
    'Indemnification Control Rule'

    __name__ = 'claim.indemnification.control.rule'

    @classmethod
    def __setup__(cls):
        super(IndemnificationControlRule, cls).__setup__()
        cls.rule.required = True
