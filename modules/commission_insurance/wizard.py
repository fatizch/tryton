# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import Pool, PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import StateView, Button

from trytond.modules.coog_core import model, fields, utils, coog_date
from trytond.modules.currency_cog import ModelCurrency
from trytond.modules.offered.extra_data import with_extra_data

from .commission import COMMISSION_RATE_DIGITS


__all__ = [
    'SimulateCommissions',
    'SimulateCommissionsParameters',
    'SimulateCommissionsParametersTermRenewal',
    'SimulateCommissionsLine',
    ]


class SimulateCommissionsParameters(model.CoogView,
        with_extra_data(['contract'])):
    'Simulate Commissions Parameters'
    __name__ = 'commission.simulate.params'

    product = fields.Many2One('offered.product', 'Product')
    contract_date = fields.Date('Contract Initial Date')
    invoice_date = fields.Date('Invoice Date')
    broker = fields.Many2One('distribution.network', 'Broker',
        domain=[('party.agents.commissioned_products', '=', Eval('product'))],
        depends=['product'])
    broker_party = fields.Many2One('party.party', 'Broker')
    agent = fields.Many2One('commission.agent', 'Agent',
        domain=[
            ('type_', '=', 'agent'),
            ('plan.commissioned_products', '=', Eval('product')),
            ('party', '=', Eval('broker_party')),
            ['OR',
                ('end_date', '>=', Eval('contract_date')),
                ('end_date', '=', None),
                ],
            ['OR',
                ('start_date', '<=', Eval('contract_date')),
                ('start_date', '=', None),
                ],
            ],
        depends=['broker_party', 'product', 'contract_date'])
    lines = fields.One2Many('commission.simulate.line', None, 'Lines')

    @classmethod
    def __setup__(cls):
        super(SimulateCommissionsParameters, cls).__setup__()
        cls._buttons.update({
                'refresh': {
                    'readonly': (~Eval('agent') | ~Eval('product')
                        | ~Eval('contract_date') | ~Eval('invoice_date')),
                }})

    @fields.depends('product', 'lines')
    def on_change_product(self):
        Line = Pool().get('commission.simulate.line')
        self.lines = []
        if self.product:
            self.lines = [Line(name=c.rec_name, premium=Decimal(100),
                    kind='premium', coverage=c.id, icon='tryton-party',
                    color='blue')
                for c in self.product.coverages]
        self.extra_data = (self.product.refresh_extra_data({})
            if self.product else {})

    @fields.depends('broker')
    def on_change_with_broker_party(self):
        return self.broker.party.id if self.broker else None

    @fields.depends('broker_party', 'product', 'contract_date')
    def on_change_with_agent(self):
        if self.product and self.contract_date:
            return utils.auto_complete_with_domain(self, 'agent')

    @fields.depends('broker', 'agent', 'product', 'contract_date',
            'invoice_date', 'lines', 'extra_data')
    def on_change_broker(self):
        self.broker_party = self.on_change_with_broker_party()
        if self.broker_party:
            self.agent = self.on_change_with_agent()
            self.on_change_agent()

    @fields.depends('broker', 'agent', 'product', 'contract_date',
            'invoice_date', 'lines', 'extra_data')
    def on_change_agent(self):
        if self.agent:
            self.refresh()

    def mock_premium(self, line, option, date):
        return Pool().get('contract.premium')(
            amount=line.premium,
            start=date,
            frequency=line.frequency,
            main_contract=option.parent_contract,
            rated_entity=option.coverage,
            taxes=option.coverage._get_taxes(),
            parent=option,
            account=option.coverage.account_for_billing)

    def mock_option(self, coverage, parent_contract, contract=None,
            covered=None):
        Option = Pool().get('contract.option')
        dates = list(parent_contract.product.get_dates(parent_contract))
        option = Option(coverage=coverage, contract=contract,
            covered_element=covered,
            initial_start_date=self.contract_date,
            start_date=self.invoice_date,
            end_date=parent_contract.end_date,
            manual_end_date=None,
            automatic_end_date=None,
            coverage_family=coverage.family if coverage else '',
            parent_contract=parent_contract,
            versions=[{'start': self.contract_date, 'extra_data': {}}],
            product=parent_contract.product,
            status='active',
            rec_name=coverage.rec_name)
        line = self.get_line(coverage)
        if not coverage.premium_rules:
            line.premium = None
            line.frequency = None
        else:
            line.frequency = coverage.premium_rules[0].frequency
        premiums = []
        for date in sorted(dates):
            if premiums:
                premiums[-1].end = coog_date.add_day(date, -1)
            premiums.append(self.mock_premium(line, option, date))
        premiums[-1].end = parent_contract.end_date
        option.premiums = premiums
        return option

    def add_option(self, instance, var_name, option):
        options = list(getattr(instance, var_name, []))
        options.append(option)
        setattr(instance, var_name, options)

    def mock_contract(self, product):
        pool = Pool()
        Contract = pool.get('contract')
        # To be able to test commission for 2nd, 3rd, ... years
        end_date = coog_date.add_year(self.contract_date, 20)
        contract = Contract(product=product, options=[],
            covered_element_options=[], agent=self.agent,
            appliable_conditions_date=self.contract_date,
            initial_start_date=self.contract_date,
            start_date=self.contract_date,
            signature_date=self.contract_date,
            end_date=end_date,
            final_end_date=end_date,
            activation_history=[{'start_date': self.contract_date,
                    'end_date': end_date}],
            block_invoicing_until=None,
            billing_informations=[{'billing_mode': product.billing_rules[-1
                        ].billing_modes[0],
                'is_once_per_contract': False, 'date': self.contract_date}],
            currency=product.currency,
            company=Transaction().context.get('company'),
            extra_datas=[{'date': self.contract_date,
                    'extra_data_values': self.extra_data}])
        return contract

    def mock(self, product):
        CoveredElement = Pool().get('contract.covered_element')
        contract = self.mock_contract(self.product)
        covered = CoveredElement(contract=contract, options=[],
            versions=[{'start': self.contract_date, 'extra_data': {}}],
            parent=None)
        contract.covered_elements = [covered]
        for coverage in self.product.coverages:
            if coverage.is_service:
                option = self.mock_option(coverage, contract, contract=contract)
                self.add_option(contract, 'options', option)
            else:
                option = self.mock_option(coverage, contract, covered=covered)
                self.add_option(covered, 'options', option)
                self.add_option(contract, 'covered_element_options', option)
        return contract

    @model.CoogView.button_change('product', 'contract_date', 'invoice_date',
        'agent', 'lines', 'extra_data')
    def refresh(self):
        with Transaction().new_transaction() as transaction:
            try:
                with transaction.set_context(_will_be_rollbacked=True):
                    self.calculate_commissions(self.mock(self.product))
                    # Used for not rollbacking those values
                    dummy = self._changed_values  # NOQA
            finally:
                transaction.rollback()

    def add_commissions(self, line, invoice, contract):
        commissions = []
        frequency = (line.frequency if line.frequency
            and line.frequency != 'once_per_invoice' else 'yearly')
        end_date = coog_date.get_end_of_period(self.invoice_date,
            frequency)
        for premium in line.get_option(contract).premiums:
            invoice_lines = premium.get_invoice_lines(self.invoice_date,
                end_date)
            if not invoice_lines:
                continue
            invoice_line = invoice_lines[0]
            invoice_line.invoice = invoice
            invoice_line.product = None
            invoice_line.amount = invoice_line.get_amount(None)
            invoice_line.principal = contract.find_insurer_agent(
                line=invoice_line)
            if not invoice_line.principal:
                continue
            for commission in invoice_line.get_commissions():
                commission.base_amount = invoice_line.amount
                commissions.append(commission)
        return commissions

    def calculate_commissions(self, contract):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoice = Invoice(currency_date=self.invoice_date,
            currency=self.product.currency, agent=self.agent, type='out',
            contract=contract)
        lines = [l for l in self.lines if l.kind == 'premium']
        n = len(lines)
        for k, line in enumerate(reversed(
                    [l for l in self.lines if l.kind == 'premium'])):
            commissions = self.add_commissions(line, invoice, contract)

            def sort_commissions(commission):
                return (commission.on_change_with_type_(),
                    commission.agent.party, commission.agent)

            sub_line = None
            for commission in reversed(
                    sorted(commissions, key=sort_commissions)):
                if (sub_line and sub_line.agent == commission.agent
                        and sub_line.date == getattr(commission, 'date', None)):
                    sub_line.init_from_commission(commission)
                else:
                    sub_line = self.new_line(line, commission,
                        contract.currency)
                    if sub_line:
                        lines.insert(n - k, sub_line)
        self.lines = lines

    def new_line(self, parent, commission, currency):
        line = Pool().get('commission.simulate.line')()
        line.currency = currency
        line.currency_digits = line.on_change_with_currency_digits()
        line.base_amount = 0
        line.init_from_commission(commission)
        return line

    def get_line(self, coverage):
        return [l for l in self.lines if l.coverage == coverage][0]


class SimulateCommissionsParametersTermRenewal(SimulateCommissionsParameters):
    __name__ = 'commission.simulate.params'
    __metaclass_ = PoolMeta

    def mock_contract(self, product):
        contract = super(SimulateCommissionsParametersTermRenewal,
            self).mock_contract(product)
        contract.activation_history[-1].final_renewal = False
        return contract


class SimulateCommissionsLine(ModelCurrency, model.CoogView):
    'Simulate Commissions Lines'
    __name__ = 'commission.simulate.line'

    premium = fields.Numeric('Premium', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    name = fields.Char('Name', readonly=True)
    kind = fields.Char('Kind', readonly=True)
    icon = fields.Char('Icon')
    color = fields.Char('Color')
    coverage = fields.Many2One('offered.option.description', 'Coverage')
    date = fields.Date('Date', readonly=True)
    party = fields.Many2One('party.party', 'Party', readonly=True)
    in_commission = fields.Numeric('In Commission',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    out_commission = fields.Numeric('Out Commission',
        digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'], readonly=True)
    base_amount = fields.Numeric('Base Amount',
        digits=(16, Eval('currency_digits', 2)), depends=['currency_digits'],
        readonly=True)
    rate = fields.Numeric('Commission Rate',
        digits=(16, COMMISSION_RATE_DIGITS), readonly=True)
    frequency = fields.Char('Frequency')
    agent = fields.Many2One('commission.agent', 'Agent')

    @classmethod
    def view_attributes(cls):
        return super(SimulateCommissionsLine, cls).view_attributes() + [
            ('/tree', 'colors', Eval('color'))]

    def get_option(self, contract):
        return [o for o in contract.get_all_options()
            if o.coverage == self.coverage][0]

    def init_from_commission(self, commission):
        self.agent = commission.agent
        self.name = '    %s' % commission.agent.plan.rec_name
        self.date = getattr(commission, 'date', None)
        self.kind = commission.on_change_with_type_()
        self.base_amount += commission.base_amount
        if self.kind == 'in':
            self.in_commission = getattr(self, 'in_commission', 0
                ) + commission.amount
            self.rate = (self.in_commission / self.base_amount).quantize(
                Decimal(10) ** -COMMISSION_RATE_DIGITS)
        else:
            self.out_commission = getattr(self, 'out_commission', 0
                ) + commission.amount
            self.rate = (self.out_commission / self.base_amount).quantize(
                Decimal(10) ** -COMMISSION_RATE_DIGITS)
        self.base_amount.quantize(Decimal(1) / 10 ** self.currency_digits)
        self.party = commission.agent.party
        self.icon = 'umbrella-blue' if self.kind == 'in' else 'coog-broker'
        self.color = 'black'


class SimulateCommissions(model.CoogWizard):
    'Simulate Commissions'

    __name__ = 'commission.simulate'

    start = StateView('commission.simulate.params',
        'commission_insurance.commission_simulate_params_view_form', [
            Button('End', 'end', 'tryton-cancel')])

    def default_start(self, values):
        active_model = Transaction().context.get('active_model')
        active_ids = Transaction().context.get('active_ids')
        if active_model == 'offered.product':
            product, = Pool().get('offered.product').browse(active_ids)
            return {
                'product': active_ids[0],
                'contract_date': utils.today(),
                'invoice_date': utils.today(),
            }
        return {}
