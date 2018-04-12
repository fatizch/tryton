# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Insurance Invoice Dunning Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.contract_insurance_invoice.tests.tools import \
    add_invoice_configuration
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.offered_insurance.tests.tools import \
    add_insurer_to_product
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.premium.tests.tools import add_premium_rules

# #Comment# #Install Modules
config = activate_modules(['contract_insurance_invoice_dunning',
        'account_payment_sepa_contract'])

# #Comment# #Create country
_ = create_country()

# #Comment# #Create currenct
currency = get_currency(code='EUR')

# #Comment# #Create Company
_ = create_company(currency=currency)
company = get_company()

# #Comment# #Reload the context
User = Model.get('res.user')
config._context = User.get_preferences(True, config.context)

# We put today in the middle of year, to not have to create several fiscal years
# when we invoice two months in the past etc.
today = datetime.date(datetime.date.today().year, 6, 1)
config._context['client_defined_date'] = today

# #Comment# #Create Fiscal Year
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company,
        today=today))
fiscalyear.click('create_period')

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)


# #Comment# #Create Fee
AccountKind = Model.get('account.account.type')
dunning_fee_kind = AccountKind()
dunning_fee_kind.name = 'Dunning Fee Account Kind'
dunning_fee_kind.company = company
dunning_fee_kind.save()
Account = Model.get('account.account')
dunning_fee_account = Account()
dunning_fee_account.name = 'Dunning Fee Account'
dunning_fee_account.code = 'dunning_fee_account'
dunning_fee_account.kind = 'revenue'
dunning_fee_account.party_required = True
dunning_fee_account.type = dunning_fee_kind
dunning_fee_account.company = company
dunning_fee_account.save()
Product = Model.get('product.product')
Template = Model.get('product.template')
template = Template()
Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
template.default_uom = unit
template.name = 'Dunning Fee Template'
template.type = 'service'
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.account_revenue = dunning_fee_account
template.save()
product_product = Product()
product_product.name = 'Dunning Fee Product'
product_product.template = template
product_product.default_uom = template.default_uom
product_product.type = 'service'
product_product.save()
Fee = Model.get('account.fee')
fee = Fee()
fee.name = 'Test Fee'
fee.code = 'test_fee'
fee.type = 'fixed'
fee.amount = Decimal('22')
fee.frequency = 'once_per_invoice'
fee.product = product_product
fee.save()

# #Comment# #Create dunning procedure
Procedure = Model.get('account.dunning.procedure')
procedure = Procedure(name='Procedure')
level = procedure.levels.new()
level.name = 'Reminder'
level.sequence = 1
level.overdue = datetime.timedelta(30)
level.apply_for = 'manual'
level = procedure.levels.new()
level.name = 'Formal Demand'
level.sequence = 2
level.overdue = datetime.timedelta(60)
level = procedure.levels.new()
level.name = 'Suspend contract'
level.sequence = 2
level.overdue = datetime.timedelta(90)
level.contract_action = 'hold'
level.dunning_fee = fee
level = procedure.levels.new()
level.name = 'Terminate contract'
level.sequence = 3
level.overdue = datetime.timedelta(100)
level.contract_action = 'terminate'
level.termination_mode = 'at_last_posted_invoice'
procedure.save()

# #Comment# #Create Product
product = init_product()
product = add_quote_number_generator(product)
product = add_premium_rules(product)
product = add_invoice_configuration(product, accounts)
product = add_insurer_to_product(product)
product.dunning_procedure = procedure
product.save()


# #Comment# #Create Subscriber
subscriber = create_party_person()

# #Comment# #Create Contract


contract_start_date = today
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=product.billing_modes[0],
        payment_term=product.billing_modes[0].allowed_payment_terms[0]))
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')
contract.billing_information.direct_debit is False
# #Res# #True

# #Comment# #Create first invoice
ContractInvoice = Model.get('contract.invoice')
Contract.first_invoice([contract.id], config.context)
first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
first_invoice.invoice.click('post')

# #Comment# #Create dunnings at 30 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=30)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning, = Dunning.find([])
dunning.contract == contract
# #Res# #True
dunning.procedure == procedure
# #Res# #True

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True
contract.dunning_status
# #Res# #u'Reminder'
dunning_contracts = Contract.find([('dunning_status', '=', 'Reminder')])
len(dunning_contracts)
# #Res# #1

# #Comment# #Create dunnings at 60 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=60)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning, = Dunning.find(['state', '=', 'draft'])

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True

# #Comment# #Create dunnings at 90 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=90)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning, = Dunning.find(['state', '=', 'draft'])

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True
contract.status == 'hold'
# #Res# #True

fee_invoice, = ContractInvoice.find([('contract', '=', contract.id),
        ('non_periodic', '=', True)])
fee_invoice.invoice.total_amount == Decimal('22')
# #Res# #True

# #Comment# #Create dunnings at 100 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=100)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning = Dunning.find([('state', '=', 'draft')])[0]

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True
contract.end_date == first_invoice.end
# #Res# #True


# TEST UPDATE OF MATURITY DATE FROM PAYMENT DATE

procedure.from_payment_date = True
procedure.save()

PaymentTerm = Model.get('account.invoice.payment_term')
PaymentTermLine = Model.get('account.invoice.payment_term.line')
payment_term = PaymentTerm()
payment_term.name = 'rest_direct'
payment_term.lines.append(PaymentTermLine())
payment_term.save()
BillingMode = Model.get('offered.billing_mode')
direct_monthly = BillingMode()
direct_monthly.name = 'direct monthly'
direct_monthly.code = 'direct_monthly'
direct_monthly.frequency = 'monthly'
direct_monthly.frequency = 'monthly'
direct_monthly.allowed_payment_terms.append(payment_term)
direct_monthly.direct_debit = True
direct_monthly.allowed_direct_debit_days = '15'
direct_monthly.save()

product.billing_modes.append(direct_monthly)
product.save()

Bank = Model.get('bank')
Party = Model.get('party.party')
party_bank = Party()
party_bank.name = 'Bank'
party_bank.save()
bank = Bank()
bank.party = party_bank
bank.bic = 'NSMBFRPPXXX'
bank.save()

Number = Model.get('bank.account.number')
Account = Model.get('bank.account')

two_months_ago = today - relativedelta(months=2)

subscriber_account = Account()
subscriber_account.bank = bank
subscriber_account.owners.append(subscriber)
subscriber_account.currency = currency
subscriber_account.number = 'BE82068896274468'
subscriber_account.save()

Mandate = Model.get('account.payment.sepa.mandate')
mandate = Mandate()
mandate.company = company
mandate.party = subscriber
mandate.account_number = subscriber_account.numbers[0]
mandate.identification = 'MANDATE'
mandate.type = 'recurrent'
mandate.signature_date = two_months_ago
mandate.save()
mandate.click('request')
mandate.click('validate_mandate')

# #Comment# #Create Payment Journal

company_account = Account()
company_account.bank = bank
company_account.owners.append(Party(company.party.id))
company_account.currency = currency
company_account.number = 'ES8200000000000000000000'
company_account.save()

Journal = Model.get('account.payment.journal')
journal = Journal()
journal.name = 'SEPA Journal'
journal.company = company
journal.currency = currency
journal.process_method = 'sepa'
journal.sepa_payable_flavor = 'pain.001.001.03'
journal.sepa_receivable_flavor = 'pain.008.001.02'
journal.sepa_charge_bearer = 'DEBT'
journal.sepa_bank_account_number = company_account.numbers[0]
journal.failure_billing_mode, = BillingMode.find([('code', '=',
    'monthly')])
journal.save()

Configuration = Model.get('account.configuration')
configuration = Configuration(1)
configuration.direct_debit_journal = journal
configuration.save()


Product = Model.get('offered.product')

contract_start_date = datetime.date(
    two_months_ago.year, two_months_ago.month, 1)
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = Product(product.id)
contract.billing_informations.append(BillingInformation(
        date=contract_start_date,
        billing_mode=BillingMode(direct_monthly.id),
        direct_debit_day=15,
        direct_debit_account=Account(subscriber_account.id),
        payer=subscriber.id,
        payment_term=BillingMode(direct_monthly.id).allowed_payment_terms[0]))
contract.contract_number = 'test_2'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')
contract.billing_information.direct_debit is True
# #Res# #True
bool(contract.billing_information.direct_debit_day) is True
# #Res# #True

ContractInvoice = Model.get('contract.invoice')
Contract.first_invoice([contract.id], config.context)
first_invoice = ContractInvoice.find(
    [('contract', '=', contract.id)],
    order=[('start', 'ASC')])[0]

config._context['client_defined_date'] = two_months_ago
first_invoice.invoice.click('post')

config._context['client_defined_date'] = today

assert all(x.maturity_date == x.payment_date
    for x in first_invoice.invoice.lines_to_pay)

Contract.rebill_contracts([contract.id], contract.start_date, config.context)

first_rebilled = ContractInvoice.find([('contract', '=', contract.id),
        ('invoice_state', '=', 'posted')],
        order=[('start', 'ASC')])[0]
first_cancelled = ContractInvoice.find([('contract', '=', contract.id),
        ('invoice_state', '=', 'cancel')],
    order=[('start', 'ASC')])[0]


def key(line):
    return line.maturity_date


cancelled_lines_to_pay = sorted(first_cancelled.invoice.lines_to_pay, key=key)
new_lines_to_pay = sorted(first_rebilled.invoice.lines_to_pay, key=key)

assert len(cancelled_lines_to_pay) == len(new_lines_to_pay) == 1

for cancelled, new in zip(cancelled_lines_to_pay, new_lines_to_pay):
    assert new.maturity_date == cancelled.maturity_date
    assert new.payment_date != cancelled.payment_date
