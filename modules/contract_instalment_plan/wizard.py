# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from dateutil.relativedelta import relativedelta

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, StateTransition, Button
from trytond.transaction import Transaction
from trytond.pyson import Eval, Bool, And, Or

from trytond.modules.coog_core import model, fields

from .instalment_plan import CALCULATION_METHOD, PAYMENT_FREQUENCY

__all__ = [
    'CreateInstalmentPlan',
    'InstalmentSelectPeriod',
    'InstalmentScheduledPayments',
    ]


class CreateInstalmentPlan(model.CoogWizard):
    'Create Instalment Plan'

    __metaclass__ = PoolMeta
    __name__ = 'contract.instalment_plan.create_instalment'

    start_state = 'start'
    start = StateTransition()
    select_period = StateView(
        'contract.instalment_plan.select_period',
        'contract_instalment_plan.select_period_view_form', [
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Schedule Payments', 'check_period', 'tryton-go-next',
                default=True,
                states={'readonly': ~Eval('contract') |
                    ~Eval('invoice_period_start') | ~Eval('invoice_period_end')
                    })
            ])
    check_period = StateTransition()
    cancel = StateTransition()
    scheduled_payments = StateView(
        'contract.instalment_plan.scheduled_payments',
        'contract_instalment_plan.scheduled_payments_view_form', [
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Select Period', 'select_period', 'tryton-go-previous'),
            Button('Suspend', 'suspend', 'tryton-save'),
            Button('Validate', 'validate_instalment', 'tryton-go-next',
                default=True)
                ])
    validate_instalment = StateTransition()
    suspend = StateTransition()

    @classmethod
    def __setup__(cls):
        super(CreateInstalmentPlan, cls).__setup__()
        cls._error_messages.update({
                'already_validated': 'It is not possible to resume an '
                'already validated instalment plan.',
                })

    @property
    def contract(self):
        return self.select_period.contract if self.select_period else None

    @property
    def instalment(self):
        if (self.scheduled_payments
                and hasattr(self.scheduled_payments, 'instalment')):
            return self.scheduled_payments.instalment
        return None

    def init_scheduled_payments_step(self):
        self.scheduled_payments.contract = self.contract
        self.scheduled_payments.invoice_period_start = \
            self.select_period.invoice_period_start
        self.scheduled_payments.invoice_period_end = \
            self.select_period.invoice_period_end
        self.scheduled_payments.company = self.contract.company
        self.scheduled_payments.currency = self.contract.company.currency
        self.scheduled_payments.currency_digits = \
            self.contract.company.currency.digits
        self.scheduled_payments.currency_symbol = \
            self.contract.company.currency.symbol

        InstalmentPlan = Pool().get('contract.instalment_plan')
        self.scheduled_payments.total_amount = \
            InstalmentPlan.calculate_total_amount(self.contract,
                self.select_period.invoice_period_start,
                self.select_period.invoice_period_end)
        self.scheduled_payments.instalment = self.update_instalment(False)
        self.scheduled_payments.scheduled_payments = \
            self.scheduled_payments.instalment.scheduled_payments

    def update_instalment(self, update_payments=True):
        pool = Pool()
        instalment = self.instalment
        if not instalment:
            InstalmentPlan = pool.get('contract.instalment_plan')
            instalment = InstalmentPlan(scheduled_payments=[])
        instalment.contract = self.contract
        instalment.company = self.contract.company
        instalment.currency = self.contract.company.currency
        instalment.currency_digits = self.contract.company.currency.digits
        instalment.currency_symbol = self.contract.company.currency.symbol
        instalment.invoice_period_start = \
            self.select_period.invoice_period_start
        instalment.invoice_period_end = self.select_period.invoice_period_end
        instalment.total_amount = self.scheduled_payments.total_amount
        if update_payments:
            to_delete = [x for x in instalment.scheduled_payments if x not in
                self.scheduled_payments.scheduled_payments]
            Payment = pool.get('contract.instalment_plan.payment')
            Payment.delete(to_delete)
            instalment.scheduled_payments = \
                [x for x in self.scheduled_payments.scheduled_payments]
        return instalment

    @classmethod
    def def_values_from_contract(cls, contract):
        if not contract:
            return None, None, None
        start_date = None
        last_invoice_date = contract.last_invoice_end
        if last_invoice_date:
            contract_end_date = contract.end_date
            if contract_end_date and (contract_end_date <= last_invoice_date):
                start_date = contract.last_invoice_start
            else:
                start_date = last_invoice_date + relativedelta(days=+1)
        if not start_date:
            start_date = contract.start_date
        periods = \
            contract.get_invoice_periods(start_date, start_date)
        if not periods:
            return contract.id, None, None
        return contract.id, periods[-1][0], periods[-1][1]

    def transition_start(self):
        pool = Pool()
        active_model = Transaction().context.get('active_model')
        if active_model == 'contract':
            Contract = pool.get(active_model)
            self.select_period.contract = Contract(
                Transaction().context.get('active_id'))
            c_id, self.select_period.invoice_period_start, \
                self.select_period.invoice_period_end = \
                self.def_values_from_contract(self.select_period.contract)
        elif active_model == 'contract.instalment_plan':
            InstalmentPlan = pool.get(active_model)
            instalment = InstalmentPlan(Transaction().context.get('active_id'))
            if instalment.state != 'draft':
                self.raise_user_error('already_validated')
            self.select_period.contract = instalment.contract
            self.select_period.invoice_period_start = \
                instalment.invoice_period_start
            self.select_period.invoice_period_end = \
                instalment.invoice_period_end
            self.scheduled_payments.instalment = instalment
            if self.select_period.check_step(instalment, False):
                self.init_scheduled_payments_step()
                return 'scheduled_payments'
            return 'check_period'
        elif active_model == 'account.invoice':
            Invoice = pool.get(active_model)
            invoices = Invoice.browse(Transaction().context.get('active_ids'))
            if invoices:
                self.select_period.contract = invoices[0].contract
                self.select_period.invoice_period_start = \
                    min([i.start for i in invoices if i.start])
                self.select_period.invoice_period_start = \
                    max([i.end for i in invoices if i.end])
        return 'select_period'

    def default_select_period(self, name):
        pool = Pool()
        active_model = Transaction().context.get('active_model')
        if active_model == 'contract':
            Contract = pool.get(active_model)
            contract = Contract(Transaction().context.get('active_id'))
            c_id, start_date, end_date = self.def_values_from_contract(contract)
            return {
                'contract': c_id,
                'invoice_period_start': start_date,
                'invoice_period_end': end_date,
                }
        elif active_model == 'contract.instalment_plan':
            InstalmentPlan = pool.get(active_model)
            instalment = InstalmentPlan(Transaction().context.get('active_id'))
            return {
                'contract': instalment.contract.id,
                'invoice_period_start': instalment.invoice_period_start,
                'invoice_period_end': instalment.invoice_period_end,
                }
        elif active_model == 'account.invoice':
            Invoice = pool.get(active_model)
            invoices = Invoice.browse(Transaction().context.get('active_ids'))
            if invoices:
                return {
                    'contract': invoices[0].contract.id,
                    'invoice_period_start':
                        min([i.start for i in invoices if i.start]),
                    'invoice_period_end':
                        max([i.end for i in invoices if i.end]),
                    }

    def transition_check_period(self):
        if self.select_period.check_step(self.instalment, True):
            self.init_scheduled_payments_step()
            return 'scheduled_payments'
        else:
            return 'select_period'

    def transition_cancel(self):
        if self.instalment:
            InstalmentPlan = Pool().get('contract.instalment_plan')
            InstalmentPlan.delete([self.instalment])
        return 'end'

    def default_scheduled_payments(self, name):
        InstalmentPlan = Pool().get('contract.instalment_plan')
        instalment = self.instalment
        contract = self.contract
        company = contract.company if contract else None
        active_model = Transaction().context.get('active_model')
        total_amount = InstalmentPlan.calculate_total_amount(contract,
                    self.select_period.invoice_period_start,
                    self.select_period.invoice_period_end)
        if active_model == 'contract.instalment_plan':
            instalment = InstalmentPlan(Transaction().context.get('active_id'))
        res = {
            'contract': contract.id if contract else None,
            'invoice_period_start': self.select_period.invoice_period_start,
            'invoice_period_end': self.select_period.invoice_period_end,
            'instalment': instalment.id if instalment else None,
            'total_amount': total_amount,
            'scheduled_payments': [x.id for x in
                instalment.scheduled_payments] if instalment else None,
            'company': company.id if company else None,
            'currency': company.currency.id if (company
                and company.currency) else None,
            'currency_digits': company.currency.digits if (company
                and company.currency) else 2,
            'currency_symbol': company.currency.symbol if (company
                and company.currency) else '',
            'calculation_method': 'based_on_frequency',
            'payment_frequency': '1',
            'nb_payments': 12,
            'first_payment_date': self.select_period.invoice_period_start,
            }
        return res

    def transition_suspend(self):
        instalment = self.update_instalment()
        if instalment:
            instalment.save()
        return 'end'

    def transition_validate_instalment(self):
        instalment = self.update_instalment()
        if instalment:
            instalment.save()
            instalment.validate_instalment([instalment])
        return 'end'


class InstalmentSelectPeriod(model.CoogView):
    'Select Invoice Period'

    __metaclass__ = PoolMeta
    __name__ = 'contract.instalment_plan.select_period'

    contract = fields.Many2One('contract', 'Contract',
        required=True, readonly=True)
    invoice_period_start = fields.Date('Invoices Period Start', required=True)
    invoice_period_end = fields.Date('Invoice Period End', required=True)

    @fields.depends('contract', 'invoice_period_start', 'invoice_period_end')
    def on_change_with_invoice_period_start(self, name=None):
        InstalmentPlan = Pool().get('contract.instalment_plan')
        return InstalmentPlan.calculate_invoice_period_start(self.contract,
            self.invoice_period_start, self.invoice_period_end)

    @fields.depends('contract', 'invoice_period_start', 'invoice_period_end')
    def on_change_with_invoice_period_end(self, name=None):
        InstalmentPlan = Pool().get('contract.instalment_plan')
        return InstalmentPlan.calculate_invoice_period_end(self.contract,
            self.invoice_period_start, self.invoice_period_end)

    def check_step(self, instlament=None, raise_error=True):
        InstalmentPlan = Pool().get('contract.instalment_plan')
        return InstalmentPlan.check_period(self.contract,
            self.invoice_period_start, self.invoice_period_end,
            instlament, raise_error)


class InstalmentScheduledPayments(model.CoogView):
    'Enter Scheduled Payments'

    __metaclass__ = PoolMeta
    __name__ = 'contract.instalment_plan.scheduled_payments'

    contract = fields.Many2One('contract', 'Contract',
        required=True, readonly=True)
    invoice_period_start = fields.Date('Invoices Period Start',
        readonly=True, required=True)
    invoice_period_end = fields.Date('Invoice Period End',
        readonly=True, required=True)
    instalment = fields.Many2One('contract.instalment_plan', 'Instalment',
        readonly=True, states={'invisible': True})
    total_amount = fields.Numeric('Total Amount',
        readonly=True, required=True, digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    company = fields.Many2One('company.company', 'Company',
        readonly=True, required=True)
    currency = fields.Many2One('currency.currency', 'Currency',
        required=True, readonly=True)
    currency_digits = fields.Integer('Currency Digits',
        required=True, readonly=True)
    currency_symbol = fields.Char('Currency Symbol',
        required=True, readonly=True)
    scheduled_payments = fields.One2Many('contract.instalment_plan.payment',
        None, 'Scheduled Payments', order=[('maturity_date', 'ASC')],
        states={
            'readonly': Eval('calculation_method') != 'manual'},
        depends=['calculation_method'])
    calculation_method = fields.Selection(CALCULATION_METHOD,
        'Calculation Method')
    payment_frequency = fields.Selection(PAYMENT_FREQUENCY, 'Frequency',
        states={
            'invisible': Eval('calculation_method') != 'based_on_frequency'},
        depends=['calculation_method'])
    first_payment_date = fields.Date('First Payment Date',
        states={
            'invisible': Eval('calculation_method') != 'based_on_frequency'},
        depends=['calculation_method'])
    nb_payments = fields.Integer('Number of Payments',
        domain=[('nb_payments', '>=', 0)],
        states={
            'invisible': Eval('calculation_method') != 'based_on_frequency'},
        depends=['calculation_method'])

    @classmethod
    def __setup__(cls):
        super(InstalmentScheduledPayments, cls).__setup__()
        cls._buttons.update({
                'calculate': {
                    'readonly': Or(
                        (~Eval('calculation_method', '')),
                        And((Eval('calculation_method', '') ==
                            'based_on_frequency'),
                            ~Eval('first_payment_date', False)),
                        And((Eval('calculation_method', '') == 'manual'),
                            Bool(Eval('scheduled_payments', False)))
                        )
                    },
                })

    @classmethod
    def view_attributes(cls):
        return super(InstalmentScheduledPayments, cls).view_attributes() + [
            ('/form/group[@id="invisible"]', 'states',
                {'invisible': True}),
            ]

    @model.CoogView.button_change('scheduled_payments', 'calculation_method',
        'first_payment_date', 'payment_frequency', 'nb_payments', 'contract',
        'invoice_period_start', 'invoice_period_end')
    def calculate(self):
        if (not self.calculation_method):
            return
        extra_args = {}
        if self.calculation_method == 'manual':
            if not self.scheduled_payments:
                extra_args['init_from_invoices'] = True
        elif self.calculation_method == 'based_on_frequency':
                extra_args['start_date'] = self.first_payment_date
                extra_args['frequency'] = self.payment_frequency
                extra_args['nb_payments'] = self.nb_payments
        InstalmentPlan = Pool().get('contract.instalment_plan')
        new_scheduled_payments = InstalmentPlan.do_calculate(self.contract,
            self.invoice_period_start, self.invoice_period_end,
            self.calculation_method, **extra_args)
        if new_scheduled_payments:
            self.scheduled_payments = new_scheduled_payments
