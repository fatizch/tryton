# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Commission Insurance Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from proteus import Model, Wizard
from decimal import Decimal
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
from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user


# #Comment# #Create Database
# config = config.set_trytond()
# config.pool.test = True
# Useful for updating the tests without having to recreate a db from scratch

# config = config.set_xmlrpc('http://admin:admin@localhost:8068/tmp_test')

# #Comment# #Install Modules
config = activate_modules('commission_insurance')

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

execute_test_case('authorizations_test_case')
config = switch_user('financial_user')

company = get_company()
# #Comment# #Create Fiscal Year
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
fiscalyear.click('create_period')

# #Comment# #Create Fiscal Year at N+1
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company,
         today=datetime.datetime.today() + relativedelta(years=1)))
fiscalyear.click('create_period')

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)

# #Comment# #Create Broker Fee Account
AccountKind = Model.get('account.account.type')
broker_fee_kind = AccountKind()
broker_fee_kind.name = 'Broker Fee Account Kind'
broker_fee_kind.company = company
broker_fee_kind.statement = 'off-balance'
broker_fee_kind.other = True
broker_fee_kind.save()
Account = Model.get('account.account')
broker_fee_account = Account()
broker_fee_account.name = 'Broker Fee Account'
broker_fee_account.code = 'broker_fee_account'
broker_fee_account.type = broker_fee_kind
broker_fee_account.party_required = True
broker_fee_account.company = company
broker_fee_account.save()
Journal = Model.get('account.journal')

cash_journal, = Journal.find([('type', '=', 'cash')])
account_cash = accounts['cash']
PaymentMethod = Model.get('account.invoice.payment.method')
payment_method = PaymentMethod()
payment_method.name = 'Cash'
payment_method.journal = cash_journal
payment_method.credit_account = account_cash
payment_method.debit_account = account_cash
payment_method.save()

config = switch_user('product_user')

Account = Model.get('account.account')


ProductCategory = Model.get('product.category')
account_category = ProductCategory(name="Account Category")
account_category.accounting = True
account_category.account_expense = Account(broker_fee_account.id)
account_category.account_revenue = Account(broker_fee_account.id)
account_category.code = 'account_category'
account_category.save()

ProductCategory = Model.get('product.category')
account_category_commission = ProductCategory(
    name="Account Category Commission")
account_category_commission.accounting = True
account_category_commission.account_expense = Account(accounts['expense'].id)
account_category_commission.account_revenue = Account(accounts['revenue'].id)
account_category_commission.code = 'account_category_commission'
account_category_commission.save()

# #Comment# #Create Broker Fee
Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
Product = Model.get('product.product')
Template = Model.get('product.template')
template = Template()
template.name = 'Broker Fee Template'
template.account_category = account_category
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.default_uom = unit
template.products[0].code = 'broker_fee_product'
template.save()
product = template.products[0]
Fee = Model.get('account.fee')
broker_fee = Fee()
broker_fee.name = 'Broker Fee'
broker_fee.code = 'broker_fee'
broker_fee.frequency = 'once_per_contract'
broker_fee.type = 'fixed'
broker_fee.amount = Decimal('20.0')
broker_fee.product = product
broker_fee.broker_fee = True
broker_fee.save()

# #Comment# #Create Product
offered_product = init_product()
offered_product = add_quote_number_generator(offered_product)
offered_product = add_premium_rules(offered_product)
offered_product = add_invoice_configuration(offered_product, accounts)
offered_product = add_insurer_to_product(offered_product)
offered_product.fees.append(broker_fee)
offered_product.save()

config = switch_user('commission_user')

company = get_company()
Plan = Model.get('commission.plan')
Product = Model.get('product.product')
Template = Model.get('product.template')
Uom = Model.get('product.uom')
ProductCategory = Model.get('product.category')
unit, = Uom.find([('name', '=', 'Unit')])
# #Comment# #Create commission product
commission_product = Product(offered_product.id)
templateComission = Template()
templateComission.name = 'Commission'
templateComission.default_uom = unit
templateComission.type = 'service'
templateComission.list_price = Decimal(0)
templateComission.cost_price = Decimal(0)
templateComission.account_category = ProductCategory(
    account_category_commission.id)
templateComission.products[0].code = 'commission_product'
templateComission.save()
commission_product = templateComission.products[0]

# #Comment# #Create commission description configuration
CommissionDescriptionConfiguration = Model.get(
    'commission.description.configuration')
descriptionConfiguration = CommissionDescriptionConfiguration()
descriptionConfiguration.linear_commission_title = \
    'Linear commission calculation details'
descriptionConfiguration.save()

# #Comment# #Create broker commission plan
Plan = Model.get('commission.plan')
Coverage = Model.get('offered.option.description')
broker_plan = Plan(name='Broker Plan')
broker_plan.commission_product = commission_product
broker_plan.commission_method = 'payment_and_accounted'
broker_plan.type_ = 'agent'
line = broker_plan.lines.new()
coverage = offered_product.coverages[0].id
line.options.append(Coverage(coverage))
line.formula = 'amount * 0.1'
broker_plan.save()

# #Comment# #Create insurer commission plan
Plan = Model.get('commission.plan')
insurer_plan = Plan(name='Insurer Plan')
insurer_plan.commission_product = commission_product
insurer_plan.commission_method = 'payment_and_accounted'
insurer_plan.type_ = 'principal'
coverage = offered_product.coverages[0].id
line = insurer_plan.lines.new()
line.options.append(Coverage(coverage))
line.formula = 'amount * 0.6'
insurer_plan.save()

# #Comment# #Create broker agent
Agent = Model.get('commission.agent')
Party = Model.get('party.party')
PaymentTerm = Model.get('account.invoice.payment_term')
broker_party = Party(name='Broker')
broker_party.supplier_payment_term, = PaymentTerm.find([])
broker_party.save()
DistributionNetwork = Model.get('distribution.network')
broker = DistributionNetwork(name='Broker', code='broker', party=broker_party)
broker.is_broker = True
broker.save()
agent_broker = Agent(party=Party(broker_party.id))
agent_broker.type_ = 'agent'
agent_broker.plan = Plan(broker_plan.id)
agent_broker.currency = company.currency
agent_broker.save()

company = get_company()
Plan = Model.get('commission.plan')
Agent = Model.get('commission.agent')
# #Comment# #Create insurer agent
Insurer = Model.get('insurer')
insurer, = Insurer.find([])
agent = Agent(party=insurer.party)
agent.type_ = 'principal'
agent.plan = Plan(insurer_plan.id)
agent.currency = company.currency
agent.save()

config = switch_user('contract_user')

Agent = Model.get('commission.agent')
OfferedProduct = Model.get('offered.product')
company = get_company()
# #Comment# #Create Subscriber
subscriber = create_party_person()
offered_product = OfferedProduct(offered_product.id)
# #Comment# #Create Test Contract
contract_start_date = datetime.date.today()
Contract = Model.get('contract')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = get_company()
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = offered_product
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=offered_product.billing_rules[-1].billing_modes[0],
        payment_term=offered_product.billing_rules[-1].billing_modes[0
            ].allowed_payment_terms[0]))
contract.contract_number = '123456789'
DistributionNetwork = Model.get('distribution.network')
contract.dist_network = DistributionNetwork(broker.id)
contract.agent = Agent(agent_broker.id)
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #Create invoice
ContractInvoice = Model.get('contract.invoice')
Contract.first_invoice([contract.id], config.context)
first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
first_invoice.invoice.total_amount == Decimal('120')
# #Res# #True
set([(x.amount, x.account.code)
    for x in first_invoice.invoice.lines]) == set([
            (Decimal('20'), 'broker_fee_account'),
            (Decimal('100'), None)])
# #Res# #True

# #Comment# #Post Invoice
first_invoice.invoice.click('post')
line = first_invoice.invoice.lines[1]
len(line.commissions)
# #Res# #2

set([(x.amount, x.commission_rate, x.agent.party.name, x.line_amount,
            x.calculation_description)
    for x in line.commissions]) == set([
            (Decimal('10'), Decimal('0.1'), 'Broker', Decimal('100'),
                'Linear commission calculation details\n'
                '10.00000000 = 100.0000 * 0.1000'),
            (Decimal('60'), Decimal('.6'), 'Insurer', Decimal('100'),
                'Linear commission calculation details\n'
                '60.00000000 = 100.0000 * 0.6000')])
# #Res# #True

# #Comment# #Pay invoice
Journal = Model.get('account.journal')
PaymentMethod = Model.get('account.invoice.payment.method')
pay = Wizard('account.invoice.pay', [first_invoice.invoice])
pay.form.payment_method = PaymentMethod(payment_method.id)
pay.execute('choice')

# #Comment# #Create commission invoice
Invoice = Model.get('account.invoice')

create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
invoice, = Invoice.find([('type', '=', 'in')])
invoice.description = 'first'
invoice.save()
invoice.total_amount == Decimal('30')
# #Res# #True
len(invoice.lines[1].broker_fee_lines)
# #Res# #1

# #Comment# #Cancel commission invoice
invoice.click('cancel')
[x.invoice_line for x in line.commissions] == [None, None]
# #Res# #True

# #Comment# #Recreate commission invoice
Invoice = Model.get('account.invoice')
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
invoice, = Invoice.find([('type', '=', 'in'),
        ('state', '!=', 'cancel')])
invoice.description = 'first'
invoice.save()
invoice.total_amount == Decimal('30')
# #Res# #True

# #Comment# #Cancel Invoice
Contract.first_invoice([contract.id], config.context)
first_invoice.invoice.state
# #Res# #'cancel'

# #Comment# #Create commission invoice
Invoice = Model.get('account.invoice')
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
invoices = Invoice.find([('type', '=', 'in')])
invoices[0].total_amount == Decimal('-30')
# #Res# #True
len(invoices[0].lines[1].broker_fee_lines)
# #Res# #1

# #Comment# #Invoice next period and pay
two_months = contract_start_date + relativedelta(months=2)
fist_two_month = datetime.date(two_months.year, two_months.month, 1)
end_next_month = fist_two_month + relativedelta(days=-1)

generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = end_next_month
generate_invoice.execute('invoice')
first_invoice, second_invoice = sorted(ContractInvoice.find([
        ('contract', '=', contract.id),
        ('invoice_state', '=', 'validated')]),
    key=lambda x: x.start)
first_invoice.invoice.click('post')
second_invoice.invoice.click('post')

# #Comment# #Pay invoice
Journal = Model.get('account.journal')
PaymentMethod = Model.get('account.invoice.payment.method')
pay = Wizard('account.invoice.pay', [first_invoice.invoice])
pay.form.payment_method = PaymentMethod(payment_method.id)
pay.execute('choice')

pay = Wizard('account.invoice.pay', [second_invoice.invoice])
pay.form.payment_method = PaymentMethod(payment_method.id)
pay.execute('choice')

# #Comment# #Create commission invoice
Invoice = Model.get('account.invoice')
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = first_invoice.end
create_invoice.execute('create_')
invoices = Invoice.find([('type', '=', 'in')])
invoices[0].total_amount == Decimal('30')
# #Res# #True
len(invoices[0].lines[1].broker_fee_lines)
# #Res# #1

# #Comment# #Create commission invoice
Invoice = Model.get('account.invoice')
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = end_next_month
create_invoice.execute('create_')
invoices = Invoice.find([('type', '=', 'in')])
invoices[0].total_amount == Decimal('10')
# #Res# #True
len(invoices[0].lines)
# #Res# #1
