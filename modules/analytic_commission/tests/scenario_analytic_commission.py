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
config = activate_modules('analytic_commission')

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

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)

# #Comment# #Create Broker Fee Account
AccountKind = Model.get('account.account.type')
broker_fee_kind = AccountKind()
broker_fee_kind.name = 'Broker Fee Account Kind'
broker_fee_kind.company = company
broker_fee_kind.save()
Account = Model.get('account.account')
broker_fee_account = Account()
broker_fee_account.name = 'Broker Fee Account'
broker_fee_account.code = 'broker_fee_account'
broker_fee_account.kind = 'other'
broker_fee_account.party_required = True
broker_fee_account.type = broker_fee_kind
broker_fee_account.company = company
broker_fee_account.save()
Journal = Model.get('account.journal')
cash_journal, = Journal.find([('type', '=', 'cash')])
cash_journal.debit_account, = Account.find(['name', '=', 'Main Cash'])
cash_journal.save()

config = switch_user('product_user')

Account = Model.get('account.account')
accounts = get_accounts(company)

# #Comment# #Create Broker Fee
Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
Product = Model.get('product.product')
Template = Model.get('product.template')
template = Template()
template.name = 'Broker Fee Template'
template.account_expense = Account(broker_fee_account.id)
template.account_revenue = Account(broker_fee_account.id)
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
offered_product = init_product(name='Product 1')
offered_product = add_quote_number_generator(offered_product)
offered_product = add_premium_rules(offered_product)
offered_product = add_invoice_configuration(offered_product, accounts)
offered_product = add_insurer_to_product(offered_product)
offered_product.fees.append(broker_fee)
offered_product.save()

# #Comment# #Create a second Product
Sequence = Model.get('ir.sequence')
OfferedProduct = Model.get('offered.product')
contract_sequence, = Sequence.find([('code', '=', 'contract')])
offered_product2 = OfferedProduct(
    name='Test Product2',
    code='Test Product2',
    company=company.id,
    currency=get_currency(code='EUR'),
    contract_generator=contract_sequence.id,
    start_date=datetime.date(2014, 1, 1))

OptionDescription = Model.get('offered.option.description')
coverage2 = OptionDescription(
    name='Coverage 2',
    code='Coverage 2',
    company=company.id,
    start_date=datetime.date(2014, 1, 1),
    currency=get_currency(code='EUR'),
    subscription_behaviour='mandatory')
offered_product2.coverages.append(coverage2)
offered_product2 = add_quote_number_generator(offered_product2)
offered_product2 = add_premium_rules(offered_product2)
BillingMode = Model.get('offered.billing_mode')
offered_product2.billing_modes.append(BillingMode.find(
        [('code', '=', 'monthly')])[0])
offered_product2.billing_modes.append(BillingMode.find(
        [('code', '=', 'monthly_direct_debit')])[0])
offered_product2.billing_modes.append(BillingMode.find(
        [('code', '=', 'quarterly')])[0])
offered_product2.billing_modes.append(BillingMode.find(
        [('code', '=', 'yearly')])[0])
for coverage in offered_product2.coverages:
    coverage.account_for_billing = Model.get('account.account')(
        accounts['revenue'].id)

insurer, = Model.get('insurer').find([])
for coverage in offered_product2.coverages:
    coverage.insurer = insurer
offered_product2.save()

config = switch_user('commission_user')

company = get_company()
Plan = Model.get('commission.plan')
Product = Model.get('product.product')
Template = Model.get('product.template')
Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
accounts = get_accounts(company)

# #Comment# #Create commission product
commission_product = Product(offered_product.id)
templateComission = Template()
templateComission.name = 'Commission'
templateComission.default_uom = unit
templateComission.type = 'service'
templateComission.list_price = Decimal(0)
templateComission.cost_price = Decimal(0)
templateComission.account_expense = accounts['expense']
templateComission.account_revenue = accounts['revenue']
templateComission.products[0].code = 'commission_product'
templateComission.save()
commission_product = templateComission.products[0]

# #Comment# #Create a second commission product
commission_product2 = Product(offered_product2.id)
templateComission2 = Template()
templateComission2.name = 'Commission2'
templateComission2.default_uom = unit
templateComission2.type = 'service'
templateComission2.list_price = Decimal(0)
templateComission2.cost_price = Decimal(0)
templateComission2.account_expense = accounts['expense']
templateComission2.account_revenue = accounts['revenue']
templateComission2.products[0].code = 'commission_product2'
templateComission2.save()
commission_product2 = templateComission2.products[0]

# #Comment# #Create broker commission plan
Plan = Model.get('commission.plan')
Coverage = Model.get('offered.option.description')
broker_plan = Plan(name='Broker Plan')
broker_plan.commission_product = commission_product
broker_plan.commission_method = 'payment'
broker_plan.type_ = 'agent'
line = broker_plan.lines.new()
coverage = offered_product.coverages[0].id
line.options.append(Coverage(coverage))
line.formula = 'amount * 0.1'
broker_plan.save()

# #Comment# #Create a second broker commission plan
broker_plan2 = Plan(name='Broker Plan 2')
broker_plan2.commission_product = commission_product2
broker_plan2.commission_method = 'payment'
broker_plan2.type_ = 'agent'
line2 = broker_plan2.lines.new()
coverage2 = offered_product2.coverages[0].id
line2.options.append(Coverage(coverage2))
line2.formula = 'amount * 0.2'
broker_plan2.save()


# #Comment# #Create a third broker commission plan
broker_plan3 = Plan(name='Broker Plan 3')
broker_plan3.commission_product = commission_product2
broker_plan3.commission_method = 'payment'
broker_plan3.type_ = 'agent'
line3 = broker_plan3.lines.new()
coverage3 = offered_product2.coverages[0].id
line3.options.append(Coverage(coverage3))
line3.formula = 'amount * 0.4'
broker_plan3.save()


# #Comment# #Create insurer commission plan
Plan = Model.get('commission.plan')
insurer_plan = Plan(name='Insurer Plan')
insurer_plan.commission_product = commission_product
insurer_plan.commission_method = 'payment'
insurer_plan.type_ = 'principal'
coverage = offered_product.coverages[0].id
line = insurer_plan.lines.new()
line.options.append(Coverage(coverage))
line.formula = 'amount * 0.6'
insurer_plan.save()


# #Comment# #Create a second insurer commission plan
insurer_plan2 = Plan(name='Insurer Plan 2')
insurer_plan2.commission_product = commission_product2
insurer_plan2.commission_method = 'payment'
insurer_plan2.type_ = 'principal'
coverage2 = offered_product2.coverages[0].id
line2 = insurer_plan2.lines.new()
line2.options.append(Coverage(coverage2))
line2.formula = 'amount * 0.6'
insurer_plan2.save()

# #Comment# #Create broker agent
Agent = Model.get('commission.agent')
Party = Model.get('party.party')
PaymentTerm = Model.get('account.invoice.payment_term')
broker_party = Party(name='Broker')
broker_party.supplier_payment_term, = PaymentTerm.find([])
broker_party.save()
DistributionNetwork = Model.get('distribution.network')
broker = DistributionNetwork(name='Broker', code='broker', party=broker_party,
    is_broker=True)
broker.save()
agent_broker = Agent(party=broker_party)
agent_broker.type_ = 'agent'
agent_broker.plan = Plan(broker_plan.id)
agent_broker.currency = company.currency
agent_broker.save()


# #Comment# #Create a second broker agent
broker_party2 = Party(name='Broker 2')
broker_party2.supplier_payment_term, = PaymentTerm.find([])
broker_party2.save()
broker2 = DistributionNetwork(name='Broker 2', code='broker2',
    party=broker_party2, is_broker=True)
broker2.save()
agent_broker2 = Agent(party=broker_party2)
agent_broker2.type_ = 'agent'
agent_broker2.plan = Plan(broker_plan2.id)
agent_broker2.currency = company.currency
agent_broker2.save()


# #Comment# #Create a third broker agent
broker_party3 = Party(name='Broker 3')
broker_party3.supplier_payment_term, = PaymentTerm.find([])
broker_party3.save()
broker3 = DistributionNetwork(name='Broker 3', code='broker3',
    party=broker_party3, is_broker=True)
broker3.save()
agent_broker3 = Agent(party=broker_party3)
agent_broker3.type_ = 'agent'
agent_broker3.plan = Plan(broker_plan3.id)
agent_broker3.currency = company.currency
agent_broker3.save()

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


# #Comment# #Create a second insurer agent
agent2 = Agent(party=insurer.party)
agent2.type_ = 'principal'
agent2.plan = Plan(insurer_plan2.id)
agent2.currency = company.currency
agent2.save()

# #Comment# #Create a third insurer agent
agent3 = Agent(party=insurer.party)
agent3.type_ = 'principal'
agent3.plan = Plan(insurer_plan2.id)
agent3.currency = company.currency
agent3.save()

config = switch_user('financial_user')
Journal = Model.get('account.journal')
Account = Model.get('account.account')

# #Comment# #Create Analytic Accounts
AnalyticAccount = Model.get('analytic_account.account')
root = AnalyticAccount()
child = AnalyticAccount()
root.name = 'ROOT'
root.code = 'root'
root.type = 'root'
root.state = 'opened'
root.save()

AnalyticLineConf = Model.get('extra_details.configuration')
child.name = 'CHILD'
child.code = 'child'
child.type = 'distribution_over_extra_details'
child.state = 'opened'
child.parent = AnalyticAccount(root.id)
child.root = AnalyticAccount(root.id)
child.pattern, = AnalyticLineConf.find([
        ('model_name', '=', 'analytic_account.line')], limit=1)
child.save()

# #Comment# #Configure analytic account to use
Configuration = Model.get('account.configuration')
configuration = Configuration(1)
configuration.broker_analytic_account_to_use = child
configuration.save()

config = switch_user('contract_user')

Agent = Model.get('commission.agent')
OfferedProduct = Model.get('offered.product')
company = get_company()
accounts = get_accounts(company)
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
contract.signature_date = contract_start_date
contract.product = offered_product
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=offered_product.billing_modes[0],
        payment_term=offered_product.billing_modes[0].allowed_payment_terms[0]))
contract.contract_number = '123456789'
DistributionNetwork = Model.get('distribution.network')
contract.dist_network = DistributionNetwork(broker.id)
contract.agent = Agent(agent_broker.id)
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #Create a second contract with same product but different month/year
# #Comment# # combination
contract2_start_date = datetime.date.today() + relativedelta(months=2)
contract2 = Contract()
contract2.company = get_company()
contract2.subscriber = subscriber
contract2.start_date = contract2_start_date
contract2.signature_date = contract2_start_date
contract2.product = offered_product
contract2.billing_informations.append(BillingInformation(date=None,
        billing_mode=offered_product.billing_modes[0],
        payment_term=offered_product.billing_modes[0].allowed_payment_terms[0]))
contract2.contract_number = '223456789'
contract2.dist_network = DistributionNetwork(broker.id)
contract2.agent = Agent(agent_broker.id)
contract2.save()
Wizard('contract.activate', models=[contract2]).execute('apply')

# #Comment# #Create a third contract with different product
offered_product2 = OfferedProduct(offered_product2.id)
contract3 = Contract()
contract3.company = get_company()
contract3.subscriber = subscriber
contract3.start_date = contract_start_date
contract3.signature_date = contract_start_date
contract3.product = offered_product2
contract3.billing_informations.append(BillingInformation(date=None,
        billing_mode=offered_product2.billing_modes[0],
        payment_term=offered_product2.billing_modes[0].allowed_payment_terms[0])
        )
contract3.contract_number = '323456789'
contract3.dist_network = DistributionNetwork(broker2.id)
contract3.agent = Agent(agent_broker2.id)
contract3.save()
Wizard('contract.activate', models=[contract3]).execute('apply')

# #Comment# #Create a fourth contract with different broker
contract4 = Contract()
contract4.company = get_company()
contract4.subscriber = subscriber
contract4.start_date = contract_start_date
contract4.signature_date = contract_start_date
contract4.product = offered_product2
contract4.billing_informations.append(BillingInformation(date=None,
        billing_mode=offered_product2.billing_modes[0],
        payment_term=offered_product2.billing_modes[0].allowed_payment_terms[0])
        )
contract4.contract_number = '423456789'
contract4.dist_network = DistributionNetwork(broker3.id)
contract4.agent = Agent(agent_broker3.id)
contract4.save()
Wizard('contract.activate', models=[contract4]).execute('apply')

# #Comment# #Create invoices
ContractInvoice = Model.get('contract.invoice')
Contract.first_invoice([contract.id], config.context)
first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
first_invoice.invoice.total_amount == Decimal('120')
# #Res# #True
set([(x.amount, x.account.code)
    for x in first_invoice.invoice.lines]) == set([
            (Decimal('20'), u'broker_fee_account'),
            (Decimal('100'), None)])
# #Res# #True

Contract.first_invoice([contract2.id], config.context)
first_invoice2, = ContractInvoice.find([('contract', '=', contract2.id)])
first_invoice2.invoice.total_amount == Decimal('120')
# #Res# #True
set([(x.amount, x.account.code)
    for x in first_invoice2.invoice.lines]) == set([
            (Decimal('20'), u'broker_fee_account'),
            (Decimal('100'), None)])
# #Res# #True


Contract.first_invoice([contract3.id], config.context)
first_invoice3, = ContractInvoice.find([('contract', '=', contract3.id)])
first_invoice3.invoice.total_amount == Decimal('100')
# #Res# #True
set([(x.amount, x.account.code)
    for x in first_invoice3.invoice.lines]) == set([
            (Decimal('100'), None)])
# #Res# #True

Contract.first_invoice([contract4.id], config.context)
first_invoice4, = ContractInvoice.find([('contract', '=', contract4.id)])
first_invoice4.invoice.total_amount == Decimal('100')
# #Res# #True
set([(x.amount, x.account.code)
    for x in first_invoice4.invoice.lines]) == set([
            (Decimal('100'), None)])
# #Res# #True

# #Comment# #Post Invoices
first_invoice.invoice.click('post')
line = first_invoice.invoice.lines[1]
len(line.commissions)
# #Res# #2
set([(x.amount, x.commission_rate, x.agent.party.name, x.line_amount)
    for x in line.commissions]) == set([
            (Decimal('10'), Decimal('.1'), u'Broker', Decimal('100')),
            (Decimal('60'), Decimal('.6'), u'Insurer', Decimal('100'))])
# #Res# #True

first_invoice2.invoice.click('post')
line2 = first_invoice2.invoice.lines[1]
len(line2.commissions)
# #Res# #2
set([(x.amount, x.commission_rate, x.agent.party.name, x.line_amount)
    for x in line2.commissions]) == set([
            (Decimal('10'), Decimal('.1'), u'Broker', Decimal('100')),
            (Decimal('60'), Decimal('.6'), u'Insurer', Decimal('100'))])
# #Res# #True


# #Comment# #Post Invoice
first_invoice3.invoice.click('post')
line3 = first_invoice3.invoice.lines[0]
len(line3.commissions)
# #Res# #2
set([(x.amount, x.commission_rate, x.agent.party.name, x.line_amount)
    for x in line3.commissions]) == set([
            (Decimal('20'), Decimal('.2'), u'Broker 2', Decimal('100')),
            (Decimal('60'), Decimal('.6'), u'Insurer', Decimal('100'))])
# #Res# #True


# #Comment# #Post Invoice
first_invoice4.invoice.click('post')
line4 = first_invoice4.invoice.lines[0]
len(line4.commissions)
# #Res# #2
set([(x.amount, x.commission_rate, x.agent.party.name, x.line_amount)
    for x in line4.commissions]) == set([
            (Decimal('40'), Decimal('.4'), u'Broker 3', Decimal('100')),
            (Decimal('60'), Decimal('.6'), u'Insurer', Decimal('100'))])
# #Res# #True


# #Comment# #Pay invoices
Journal = Model.get('account.journal')
pay = Wizard('account.invoice.pay',
    [first_invoice.invoice])
pay.form.journal = Journal(cash_journal.id)
pay.execute('choice')

pay2 = Wizard('account.invoice.pay',
    [first_invoice2.invoice])
pay2.form.journal = Journal(cash_journal.id)
pay2.execute('choice')

pay3 = Wizard('account.invoice.pay',
    [first_invoice3.invoice])
pay3.form.journal = Journal(cash_journal.id)
pay3.execute('choice')

pay4 = Wizard('account.invoice.pay',
    [first_invoice4.invoice])
pay4.form.journal = Journal(cash_journal.id)
pay4.execute('choice')


config = switch_user('financial_user')

# #Comment# #Create commission invoice
Invoice = Model.get('account.invoice')
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
invoices = Invoice.find([('business_kind', '=', 'broker_invoice')])
for invoice in invoices:
    invoice.invoice_date = datetime.date.today()
    invoice.click('validate_invoice')
    invoice.click('post')

AnalyticLine = Model.get('analytic_account.line')
analytic_lines = AnalyticLine.find([])
[(x.credit, x.debit) for x in analytic_lines] == [
    (Decimal('0'), Decimal('40')),
    (Decimal('0'), Decimal('20')),
    (Decimal('0'), Decimal('10')),
    (Decimal('0'), Decimal('10'))
    ]
# #Res# #True

[x.extra_details for x in analytic_lines] == [
    {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 3,
        u'commissioned_contract_product': 2
    }, {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 2,
        u'commissioned_contract_product': 2
    }, {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 1,
        u'commissioned_contract_product': 1
    }, {
        u'commissioned_contract_signature_month': '201810',
        u'commissioned_contract_broker': 1,
        u'commissioned_contract_product': 1
    }, ]
# #Res# #True

for invoice in invoices:
    invoice.click('cancel')

all_analytic_lines = AnalyticLine.find([])

[(x.credit, x.debit) for x in all_analytic_lines] == [
    (Decimal('0'), Decimal('40')),
    (Decimal('0'), Decimal('20')),
    (Decimal('0'), Decimal('10')),
    (Decimal('0'), Decimal('10')),
    (Decimal('40'), Decimal('0')),
    (Decimal('20'), Decimal('0')),
    (Decimal('10'), Decimal('0')),
    (Decimal('10'), Decimal('0'))
    ]
# #Res# #True

[x.extra_details for x in all_analytic_lines] == [
    {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 3,
        u'commissioned_contract_product': 2
    }, {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 2,
        u'commissioned_contract_product': 2
    }, {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 1,
        u'commissioned_contract_product': 1
    }, {
        u'commissioned_contract_signature_month': '201810',
        u'commissioned_contract_broker': 1,
        u'commissioned_contract_product': 1
    },
    {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 3,
        u'commissioned_contract_product': 2
    }, {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 2,
        u'commissioned_contract_product': 2
    }, {
        u'commissioned_contract_signature_month': u'201808',
        u'commissioned_contract_broker': 1,
        u'commissioned_contract_product': 1
    }, {
        u'commissioned_contract_signature_month': '201810',
        u'commissioned_contract_broker': 1,
        u'commissioned_contract_product': 1
    }, ]
# #Res# #True
