# -*- coding:utf-8 -*-
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Or, Bool
from trytond.model import ModelView
from trytond.rpc import RPC

from trytond.modules.cog_utils import fields, model, coop_string, utils, \
    coop_date
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.claim_indemnification.benefit import \
    INDEMNIFICATION_DETAIL_KIND
from trytond.modules.claim_indemnification.benefit import INDEMNIFICATION_KIND
from trytond.modules.currency_cog.currency import DEF_CUR_DIG
from trytond.modules.rule_engine import RuleMixin

__metaclass__ = PoolMeta
__all__ = [
    'Claim',
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

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._buttons.update({
                'button_calculate': {
                    'invisible': Eval('status').in_(['closed']),
                    }
                })

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

    @classmethod
    def __setup__(cls):
        super(ClaimService, cls).__setup__()
        cls.__rpc__.update({
                'create_indemnification': RPC(instantiate=0,
                    readonly=False),
                'fill_extra_datas': RPC(instantiate=0,
                    readonly=False),
                })

    @classmethod
    def _export_skips(cls):
        return super(ClaimService, cls)._export_skips() | {'multi_level_view'}

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

    def get_paid_until_date(self, name):
        return None

    @classmethod
    def default_period_frequency(cls):
        return 'quarterly'

    def init_from_loss(self, loss, benefit):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')
        super(ClaimService, self).init_from_loss(loss, benefit)
        if self.loss.start_date and self.loss.end_date:
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
            details_dict['regularization'] = [
                {
                    'amount_per_unit': amount,
                    'nb_of_unit': -1,
                }]

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
    customer = fields.Many2One('party.party', 'Customer', ondelete='RESTRICT',
        states={'readonly': Eval('status') == 'paid'}, depends=['status'])
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

    def get_benefit_description(self, name):
        if self.service and self.service.benefit:
            return self.service.benefit.rec_name
        return ''

    def init_from_service(self, service):
        self.status = 'calculated'
        self.service = service
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
        return config.control_rule.calculate(ctx)

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
    @ModelView.button
    def schedule(cls, indemnifications):
        Event = Pool().get('event')
        for indemnification in indemnifications:
            do_control, reason = indemnification.require_control()
            if do_control is True:
                cls.write([indemnification], {
                    'status': 'scheduled', 'control_reason': reason})
            else:
                cls.write([indemnification], {'status': 'controlled'})
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
    @ModelView.button
    def validate_indemnification(cls, indemnifications):
        cls.write(indemnifications, {'status': 'validated'})
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
        Invoice = pool.get('account.invoice')
        indemnification = indemnifications[0].id
        invoices_to_cancel = Invoice.search([
                ('lines.claim_details.indemnification', '=', indemnification)])
        Invoice.cancel(invoices_to_cancel)
        cls.write(indemnifications, {'status': 'cancelled'})

    @classmethod
    def control_indemnification(cls, indemnifications):
        cls.write(indemnifications, {'status': 'controlled'})

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
        if party.supplier_payment_term:
            payment_term = party.supplier_payment_term
        else:
            payment_term = PaymentTerm.search([])[0]
        return Invoice(
            company=key['company'],
            type='in_invoice',
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
        for indemnification in indemnifications:
            key = {
                'party': indemnification.beneficiary,
                'product': indemnification.service.benefit.account_product,
                'company': indemnification.service.contract.company,
                'currency': indemnification.currency,
                'indemnification': indemnification,
                }
            invoice = cls._get_invoice(key)
            invoice.lines = [cls._get_invoice_line(key, invoice,
                    indemnification)]
            if indemnification.taxes:
                cls.add_taxes_to_invoice(invoice, indemnification.taxes,
                    indemnification.amount)
            invoices.append(invoice)
        Invoice.save(invoices)
        Invoice.post(invoices)
        cls.write(indemnifications, {'status': 'paid'})


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


class IndemnificationControlRule(RuleMixin, model.CoopSQL, model.CoopView):
    'Indemnification Control Rule'

    __name__ = 'claim.indemnification.control.rule'
