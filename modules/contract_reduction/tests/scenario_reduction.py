# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Start Date Endorsement Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules

from trytond.exceptions import UserError, UserWarning
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import get_accounts, create_chart
from trytond.modules.currency.tests.tools import get_currency

from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user


# #Comment# #Tools
def test_error(error_class, func, *func_args, **func_kwargs):
    try:
        func(*func_args, **func_kwargs)
        raise Exception('Expected error was not raised')
    except error_class:
        pass


# #Comment# #Install Modules
config = activate_modules(['contract_insurance_invoice', 'contract_reduction'])

# #Comment# #Constants
product_start_date = datetime.date(2014, 1, 1)
contract_start_date = datetime.date(2014, 4, 10)
contract_reduction_date = datetime.date(2014, 10, 31)
config._context['client_defined_date'] = contract_reduction_date + \
    relativedelta(days=1)

# #Comment# #Create or fetch Currency
currency = get_currency(code='EUR')

# #Comment# #Create or fetch Country
Country = Model.get('country.country')
countries = Country.find([('code', '=', 'FR')])
if not countries:
    country = Country(name='France', code='FR')
    country.save()

# #Comment# #Create Company
_ = create_company(currency=currency)

# #Comment# #Switch user
execute_test_case('authorizations_test_case')
config = switch_user('financial_user')
company = get_company()

Account = Model.get('account.account')
AccountInvoice = Model.get('account.invoice')
AccountKind = Model.get('account.account.type')
FiscalYear = Model.get('account.fiscalyear')
InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
Sequence = Model.get('ir.sequence')
SequenceStrict = Model.get('ir.sequence.strict')

# #Comment# #Create Fiscal Year
fiscalyear = FiscalYear(name='2014')
fiscalyear.start_date = datetime.date(contract_start_date.year, 1, 1)
fiscalyear.end_date = datetime.date(contract_start_date.year, 12, 31)
fiscalyear.company = company
post_move_seq = Sequence(name='2014', code='account.move',
    company=company)
post_move_seq.save()
fiscalyear.post_move_sequence = post_move_seq
seq = SequenceStrict(name='2014',
    code='account.invoice', company=company)
seq.save()
bool(fiscalyear.invoice_sequences.pop())
# #Res# #True

fiscalyear.save()
invoice_sequence = InvoiceSequence()
invoice_sequence.out_invoice_sequence = seq
invoice_sequence.in_invoice_sequence = seq
invoice_sequence.out_credit_note_sequence = seq
invoice_sequence.in_credit_note_sequence = seq
invoice_sequence.fiscalyear = fiscalyear
invoice_sequence.company = company
invoice_sequence.save()

fiscalyear.reload()
FiscalYear.create_period([fiscalyear.id], config.context)
_ = create_chart(company)

# #Comment# #Create Account Kind
product_account_kind = AccountKind()
product_account_kind.name = 'Product Account Kind'
product_account_kind.company = company
product_account_kind.statement = 'income'
product_account_kind.revenue = True
product_account_kind.save()
receivable_account_kind = AccountKind()
receivable_account_kind.name = 'Receivable Account Kind'
receivable_account_kind.company = company
receivable_account_kind.statement = 'balance'
receivable_account_kind.receivable = True
receivable_account_kind.save()
payable_account_kind = AccountKind()
payable_account_kind.name = 'Payable Account Kind'
payable_account_kind.company = company
payable_account_kind.statement = 'balance'
payable_account_kind.payable = True
payable_account_kind.save()

# #Comment# #Create Account
product_account = Account()
product_account.name = 'Product Account'
product_account.code = 'product_account'
product_account.type = product_account_kind
product_account.company = company
product_account.save()
receivable_account = Account()
receivable_account.name = 'Account Receivable'
receivable_account.code = 'account_receivable'
receivable_account.type = receivable_account_kind
receivable_account.reconcile = True
receivable_account.company = company
receivable_account.party_required = True
receivable_account.save()

payable_account = Account()
payable_account.name = 'Account Payable'
payable_account.code = 'account_payable'
payable_account.type = payable_account_kind
payable_account.company = company
payable_account.party_required = True
payable_account.save()


config = switch_user('product_user')

company = get_company()
currency = get_currency(code='EUR')
Account = Model.get('account.account')
PaymentTerm = Model.get('account.invoice.payment_term')
PaymentTermLine = Model.get('account.invoice.payment_term.line')
BillingMode = Model.get('offered.billing_mode')
Product = Model.get('offered.product')
SequenceType = Model.get('ir.sequence.type')
Sequence = Model.get('ir.sequence')
OptionDescription = Model.get('offered.option.description')
RuleEngine = Model.get('rule_engine')
RuleEngineContext = Model.get('rule_engine.context')

# #Comment# #Create reduction rule
funeral_reduction_rule = RuleEngine()
funeral_reduction_rule.context = RuleEngineContext(1)
funeral_reduction_rule.name = 'Reduction Rule'
funeral_reduction_rule.short_name = 'reduction_rule'
funeral_reduction_rule.status = 'validated'
funeral_reduction_rule.type_ = 'reduction'
funeral_reduction_rule.algorithm = 'return 123.45'
funeral_reduction_rule.save()

# #Comment# #Create reduction eligibility rule
funeral_reduction_eligibility_rule = RuleEngine()
funeral_reduction_eligibility_rule.context = RuleEngineContext(1)
funeral_reduction_eligibility_rule.name = 'Reduction Eligibility Rule'
funeral_reduction_eligibility_rule.short_name = 'reduction_eligibility_rule'
funeral_reduction_eligibility_rule.status = 'validated'
funeral_reduction_eligibility_rule.type_ = 'reduction_eligibility'
algorithm = 'date = date_de_calcul()'
algorithm += '\nreturn (date + relativedelta(days=1)).day == 1'
funeral_reduction_eligibility_rule.algorithm = algorithm
funeral_reduction_eligibility_rule.save()

# #Comment# #Create billing modes
payment_term = PaymentTerm()
payment_term.name = 'direct'
payment_term.lines.append(PaymentTermLine())
payment_term.save()
freq_monthly = BillingMode()
freq_monthly.name = 'Monthly'
freq_monthly.code = 'monthly'
freq_monthly.frequency = 'monthly'
freq_monthly.allowed_payment_terms.append(payment_term)
freq_monthly.save()
freq_yearly = BillingMode()
freq_yearly.name = 'Yearly'
freq_yearly.code = 'yearly'
freq_yearly.frequency = 'yearly'
freq_yearly.allowed_payment_terms.append(PaymentTerm.find([])[0])
freq_yearly.save()

# #Comment# #Create Product
sequence_code = SequenceType()
sequence_code.name = 'Product sequence'
sequence_code.code = 'contract'
sequence_code.company = company
sequence_code.save()
contract_sequence = Sequence()
contract_sequence.name = 'Contract Sequence'
contract_sequence.code = sequence_code.code
contract_sequence.company = company
contract_sequence.save()
quote_sequence_code = SequenceType()
quote_sequence_code.name = 'Product sequence'
quote_sequence_code.code = 'quote'
quote_sequence_code.company = company
quote_sequence_code.save()
quote_sequence = Sequence()
quote_sequence.name = 'Quote Sequence'
quote_sequence.code = quote_sequence_code.code
quote_sequence.company = company
quote_sequence.save()
coverage = OptionDescription()
coverage.company = company
coverage.currency = currency
coverage.name = 'Test Coverage'
coverage.code = 'test_coverage'
coverage.start_date = product_start_date
coverage.account_for_billing, = Account.find(
        [('code', '=', 'product_account')])
reduction = coverage.reduction_rules.new()
reduction.rule = funeral_reduction_rule
reduction.eligibility_rule = funeral_reduction_eligibility_rule
coverage.save()

accounts = get_accounts(company)

# #Comment# #Create Contract Fee
ProductCategory = Model.get('product.category')
account_category = ProductCategory(name="Account Category")
account_category.accounting = True
account_category.account_expense = accounts['expense']
account_category.account_revenue = accounts['revenue']
account_category.code = 'account_category_1'
account_category.save()

Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
AccountProduct = Model.get('product.product')
Template = Model.get('product.template')
template = Template()
template.name = 'contract Fee Template'
template.default_uom = unit
template.account_category = account_category
template.type = 'service'
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.products[0].code = 'contract Fee product'
template.save()
fee_product = template.products[0]
Fee = Model.get('account.fee')
contract_fee = Fee()
contract_fee.name = 'contract Fee'
contract_fee.code = 'contract_fee'
contract_fee.frequency = 'at_contract_signature'
contract_fee.type = 'fixed'
contract_fee.amount = Decimal('800.0')
contract_fee.product = fee_product
contract_fee.save()


product = Product()
product.company = company
product.currency = currency
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.start_date = product_start_date
product.billing_rules[-1].billing_modes.append(freq_monthly)
product.billing_rules[-1].billing_modes.append(freq_yearly)
product.coverages.append(coverage)
product.fees.append(contract_fee)
product.save()

config = switch_user('contract_user')

config._context['client_defined_date'] = contract_reduction_date + \
    relativedelta(days=1)

Account = Model.get('account.account')
BillingInformation = Model.get('contract.billing_information')
BillingMode = Model.get('offered.billing_mode')
Contract = Model.get('contract')
ContractInvoice = Model.get('contract.invoice')
ContractPremium = Model.get('contract.premium')
Option = Model.get('contract.option')
OptionDescription = Model.get('offered.option.description')
Party = Model.get('party.party')
PaymentTerm = Model.get('account.invoice.payment_term')
SubStatus = Model.get('contract.sub_status')
product = Model.get('offered.product')(product.id)
company = get_company()

# #Comment# #Create Subscriber
subscriber = Party()
subscriber.name = 'Doe'
subscriber.first_name = 'John'
subscriber.is_person = True
subscriber.gender = 'male'
subscriber.account_receivable = Account(receivable_account.id)
subscriber.account_payable = Account(payable_account.id)
subscriber.birth_date = datetime.date(1980, 10, 14)
subscriber.save()

# #Comment# #Create Test Contract
freq_yearly = BillingMode(freq_yearly.id)
payment_term = PaymentTerm(payment_term.id)

contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.status = 'quote'
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=freq_yearly, payment_term=payment_term))
contract.save()

product_account, = Account.find([('code', '=', 'product_account')])
coverage = OptionDescription(coverage.id)
Wizard('contract.activate', models=[contract]).execute('apply')
premium = contract.options[0].premiums.new()
premium.start = contract_start_date
premium.amount = Decimal('100')
premium.frequency = 'monthly'
premium.account = product_account
premium.rated_entity = coverage
contract.save()

# #Comment# #Check generated fee invoice
fee_invoice, = AccountInvoice.find([('start', '=', None)])
fee_invoice.start is None
# #Res# #True
fee_invoice.end is None
# #Res# #True
fee_invoice.total_amount == Decimal(800)
# #Res# #True
fee_invoice.state == 'posted'
# #Res# #True

# #Comment# #Generate first periodic invoice
Rebill = Wizard('contract.do_invoice', [contract])
Rebill.form.up_to_date == contract.start_date
# #Res# #True

_ = Rebill.execute('invoice')
contract.reload()

first_invoice, = AccountInvoice.find([('start', '!=', None)])
first_invoice.start == contract_start_date
# #Res# #True
first_invoice.end == contract_start_date + relativedelta(years=1, days=-1)
# #Res# #True
first_invoice.total_amount == Decimal(1200)
# #Res# #True
first_invoice.state == 'validated'
# #Res# #True

# #Comment# #Reduce contract
ReductionWizard = Wizard('contract.reduce', [contract])
ReductionWizard.form.reduction_date = contract_reduction_date + \
    relativedelta(days=1)

# The rule refuses reduction if the date is not the last day of a month
test_error(UserError, ReductionWizard.execute, 'calculate')

ReductionWizard.form.reduction_date = contract_reduction_date
ReductionWizard.execute('calculate')
ReductionWizard.form.reduction_value == Decimal('123.45')
# #Res# #True

# There is a warning when reducing a contract
test_error(UserWarning, ReductionWizard.execute, 'reduce')

Warning = Model.get('res.user.warning')
User = Model.get('res.user')

warning = Warning()
warning.always = False
warning.user = User(config.user)
warning.name = 'will_reduce_[%s]' % str(contract.id)
warning.save()

ReductionWizard.execute('reduce')
contract.reload()

# #Comment# #Check reduction consequences
contract.status == 'active'
# #Res# #True
contract.sub_status.code == 'contract_active_reduced'
# #Res# #True
contract.reduction_date == contract_reduction_date
# #Res# #True
contract.options[0].status == 'active'
# #Res# #True
contract.options[0].sub_status is None
# #Res# #True
contract.options[0].reduction_value == Decimal('123.45')
# #Res# #True
contract.can_reduce is False  # Already reduced
# #Res# #True

fee_invoice, = AccountInvoice.find([('start', '=', None)])
fee_invoice.start is None
# #Res# #True
fee_invoice.end is None
# #Res# #True
fee_invoice.total_amount == Decimal(800)
# #Res# #True
fee_invoice.state == 'posted'
# #Res# #True

reduction_invoice, = AccountInvoice.find([('start', '!=', None)])
reduction_invoice.start == contract_start_date
# #Res# #True
reduction_invoice.end == contract_reduction_date
# #Res# #True

# 6 full months at 100 + 22 / 31 for the last one
reduction_invoice.total_amount == Decimal('670.97')
# #Res# #True
reduction_invoice.state == 'posted'
# #Res# #True

# #Comment# #Cancel reduction
test_error(UserWarning, Wizard, 'contract.cancel.reduction', [contract])

warning = Warning()
warning.always = False
warning.user = User(config.user)
warning.name = 'will_cancel_reduction_[%s]' % str(contract.id)
warning.save()

Cancel = Wizard('contract.cancel.reduction', [contract])
contract.reload()

contract.status == 'active'
# #Res# #True
contract.reduction_date is None
# #Res# #True
contract.sub_status is None
# #Res# #True
contract.end_date is None
# #Res# #True
contract.initial_start_date == contract_start_date
# #Res# #True
contract.options[0].status == 'active'
# #Res# #True
contract.options[0].sub_status is None
# #Res# #True
contract.options[0].reduction_value is None
# #Res# #True

fee_invoice, = AccountInvoice.find([('start', '=', None)])
fee_invoice.start is None
# #Res# #True
fee_invoice.end is None
# #Res# #True
fee_invoice.total_amount == Decimal(800)
# #Res# #True
fee_invoice.state == 'posted'
# #Res# #True

reduction_invoice, = AccountInvoice.find(
        [('start', '!=', None), ('state', '=', 'cancel')])
reduction_invoice.start == contract_start_date
# #Res# #True
reduction_invoice.end == contract_reduction_date
# #Res# #True
reduction_invoice.total_amount == Decimal('670.97')
# #Res# #True

rebill_invoice, = AccountInvoice.find(
        [('start', '!=', None), ('state', '=', 'posted')])
rebill_invoice.start == contract_start_date
# #Res# #True
rebill_invoice.end == contract_start_date + relativedelta(
        years=1, days=-1)
# #Res# #True
rebill_invoice.total_amount == Decimal('1200')
# #Res# #True

# #Comment# #Check automatic reduction
Terminate = Wizard('contract.stop', [contract])
Terminate.form.status = 'terminated'
Terminate.form.sub_status, = SubStatus.find([('code', '=', 'terminated')])
Terminate.form.at_date = contract_reduction_date
[x.id for x in Terminate.form.contracts] == [contract.id]
# #Res# #True

# First warning: automatic reduction
test_error(UserWarning, Terminate.execute, 'stop')

warning = Warning()
warning.always = False
warning.user = User(config.user)
warning.name = 'auto_reducing_%s' % str(contract.id)
warning.save()

# Second warning: reduction going on
test_error(UserWarning, Terminate.execute, 'stop')

warning = Warning()
warning.always = False
warning.user = User(config.user)
warning.name = 'will_reduce_[%s]' % str(contract.id)
warning.save()

Terminate.execute('stop')

contract.status == 'active'
# #Res# #True
contract.sub_status.code == 'contract_active_reduced'
# #Res# #True
contract.reduction_date == contract_reduction_date
# #Res# #True
contract.options[0].status == 'active'
# #Res# #True
contract.options[0].sub_status is None
# #Res# #True
contract.options[0].reduction_value == Decimal('123.45')
# #Res# #True
contract.can_reduce is False  # Already reduced
# #Res# #True

fee_invoice, = AccountInvoice.find([('start', '=', None)])
fee_invoice.start is None
# #Res# #True
fee_invoice.end is None
# #Res# #True
fee_invoice.total_amount == Decimal(800)
# #Res# #True
fee_invoice.state == 'posted'
# #Res# #True

previous_reduction_invoice, cancelled_periodic_invoice = AccountInvoice.find(
        [('start', '!=', None), ('state', '=', 'cancel')],
        order=[('id', 'ASC')])
previous_reduction_invoice.start == contract_start_date
# #Res# #True
previous_reduction_invoice.end == contract_reduction_date
# #Res# #True
previous_reduction_invoice.total_amount == Decimal('670.97')
# #Res# #True
previous_reduction_invoice.state == 'cancel'
# #Res# #True

cancelled_periodic_invoice.start == contract_start_date
# #Res# #True
cancelled_periodic_invoice.end == contract_start_date + relativedelta(
    years=1, days=-1)
# #Res# #True
cancelled_periodic_invoice.total_amount == Decimal(1200)
# #Res# #True
cancelled_periodic_invoice.state == 'cancel'
# #Res# #True

new_reduction_invoice, = AccountInvoice.find(
        [('start', '!=', None), ('state', '=', 'posted')])
new_reduction_invoice.start == contract_start_date
# #Res# #True
new_reduction_invoice.end == contract_reduction_date
# #Res# #True
new_reduction_invoice.total_amount == Decimal('670.97')
# #Res# #True
new_reduction_invoice.state == 'posted'
# #Res# #True
