# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Commission Prepayment Scenario
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
from trytond.modules.premium.tests.tools import add_premium_rules
from trytond.modules.country_cog.tests.tools import create_country


# #Comment# #Install Modules
config = activate_modules('commission_insurance_prepayment')

# #Comment# #Create country
_ = create_country()

# #Comment# #Create currency
currency = get_currency(code='EUR')

# #Comment# #Create Company
_ = create_company(currency=currency)
company = get_company()

# #Comment# #Reload the context
User = Model.get('res.user')
config._context = User.get_preferences(True, config.context)

# #Comment# #Create Fiscal Year
base_year = 2015
while base_year <= datetime.date.today().year + 1:
    fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(
        company, today=datetime.date(base_year, 1, 1)))
    fiscalyear.click('create_period')
    base_year += 1

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)

# #Comment# #Create Product
product = init_product()
product = add_quote_number_generator(product)
product = add_premium_rules(product)
product = add_invoice_configuration(product, accounts)
product = add_insurer_to_product(product)
product.save()

# #Comment# #Create commission product
Uom = Model.get('product.uom')
Template = Model.get('product.template')
Product = Model.get('product.product')
unit, = Uom.find([('name', '=', 'Unit')])
template = Template()
template.name = 'Commission'
template.default_uom = unit
template.type = 'service'
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.account_expense = accounts['expense']
template.account_revenue = accounts['revenue']
template.products[0].code = 'commission_product'
template.save()

commission_product = template.products[0]

products = Product.find([])

# #Comment# #Create broker commission plan
Plan = Model.get('commission.plan')
Coverage = Model.get('offered.option.description')
broker_plan = Plan(name='Broker Plan')
broker_plan.commission_product = commission_product
broker_plan.commission_method = 'posting'
broker_plan.type_ = 'agent'
line = broker_plan.lines.new()
coverage = product.coverages[0].id
line.options.append(Coverage(coverage))
line.formula = 'amount * 0.6'
line.prepayment_formula = 'first_year_premium * 0.6'
broker_plan.save()

# #Comment# #Create insurer commission plan
Plan = Model.get('commission.plan')
insurer_plan = Plan(name='Insurer Plan')
insurer_plan.commission_product = commission_product
insurer_plan.commission_method = 'payment'
insurer_plan.type_ = 'principal'
coverage = product.coverages[0].id
line = insurer_plan.lines.new()
line.options.append(Coverage(coverage))
line.formula = 'amount * 0.3'
line.prepayment_formula = 'first_year_premium * 0.3'
insurer_plan.save()

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
agent_broker.plan = broker_plan
agent_broker.currency = company.currency
agent_broker.save()

# #Comment# #Create insurer agent
Insurer = Model.get('insurer')
insurer, = Insurer.find([])
agent = Agent(party=insurer.party)
agent.type_ = 'principal'
agent.plan = insurer_plan
agent.currency = company.currency
agent.save()

# #Comment# #Create Subscriber
subscriber = create_party_person()

# #Comment# #Create Test Contract
contract_start_date = datetime.date(2015, 1, 1)
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.options[0].premiums.append(ContractPremium(start=contract_start_date,
        amount=Decimal('100'), frequency='monthly',
        account=accounts['revenue'], rated_entity=Coverage(coverage)))
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=product.billing_modes[0],
        payment_term=product.billing_modes[0].allowed_payment_terms[0]))
contract.contract_number = '123456789'
DistributionNetwork = Model.get('distribution.network')
contract.dist_network = DistributionNetwork(broker.id)
contract.agent = agent_broker
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #Check prepayment commission creation
Commission = Model.get('commission')
commissions = Commission.find([()])
[(x.amount, x.commission_rate, x.is_prepayment, x.redeemed_prepayment,
    x.base_amount, x.agent.party.name) for x in commissions] == [
    (Decimal('720.0000'), Decimal('.6'), True, None, Decimal('1200.0000'),
        'Broker'),
    (Decimal('360.0000'), Decimal('.3'), True, None, Decimal('1200.0000'),
        'Insurer')]
# #Res# #True

# #Comment# #Create invoices
ContractInvoice = Model.get('contract.invoice')
until_date = contract_start_date + relativedelta(years=1)
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')
contract_invoices = contract.invoices
first_invoice = contract_invoices[-1]
first_invoice.invoice.total_amount
# #Res# #Decimal('100.00')

# #Comment# #Post Invoices
for contract_invoice in contract_invoices[::-1]:
    contract_invoice.invoice.click('post')

# #Comment# #Validate first invoice commissions
first_invoice = contract_invoices[-1]
line, = first_invoice.invoice.lines
len(line.commissions)
# #Res# #2
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in line.commissions] == [
    (Decimal('0.0000'), False, Decimal('60.0000'), Decimal('100.0000'),
        'Broker'),
    (Decimal('0.0000'), False, Decimal('30.0000'), Decimal('100.0000'),
        'Insurer')]
# #Res# #True

# #Comment# #Validate last invoice of the year commissions
last_invoice = contract_invoices[1]
line, = last_invoice.invoice.lines
len(line.commissions)
# #Res# #2
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in line.commissions] == [
    (Decimal('0.0000'), False, Decimal('60.0000'), Decimal('100.0000'),
        'Broker'),
    (Decimal('0.0000'), False, Decimal('30.0000'), Decimal('100.0000'),
        'Insurer')]
# #Res# #True

# #Comment# #Validate first invoice of next year commissions
first_invoice = contract_invoices[0]
line, = first_invoice.invoice.lines
len(line.commissions)
# #Res# #2
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in line.commissions] == [
    (Decimal('60.0000'), False, Decimal('0.0000'), Decimal('100.0000'),
        'Broker'),
    (Decimal('30.0000'), False, Decimal('0.0000'), Decimal('100.0000'),
        'Insurer')]
# #Res# #True

# #Comment# #Generate insurer and broker invoice
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
Invoice = Model.get('account.invoice')
invoice, = Invoice.find([('type', '=', 'in')])

# #Comment# #Cancel invoice
first_invoice.click('cancel')
last_invoice.click('cancel')
line, = last_invoice.invoice.lines
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in line.commissions] == [
    (Decimal('0.0000'), False, Decimal('60.0000'), Decimal('100.0000'),
        'Broker'),
    (Decimal('0.0000'), False, Decimal('30.0000'), Decimal('100.0000'),
        'Insurer'),
    (Decimal('0.0000'), False, Decimal('-30.0000'), Decimal('-100.0000'),
        'Insurer'),
    (Decimal('0.0000'), False, Decimal('-60.0000'), Decimal('-100.0000'),
        'Broker')]
# #Res# #True

# #Comment# #Terminate Contract
end_date = contract_start_date + relativedelta(months=7, days=-1)
config._context['client_defined_date'] = end_date + relativedelta(days=1)
SubStatus = Model.get('contract.sub_status')
sub_status = SubStatus()
sub_status.name = 'Client termination'
sub_status.code = 'client_termination'
sub_status.status = 'terminated'
sub_status.save()

end_contract = Wizard('contract.stop', models=[contract])
end_contract.form.status = 'terminated'
end_contract.form.at_date = end_date
end_contract.form.sub_status = sub_status
end_contract.execute('stop')

# #Comment# #Check commission once terminated
commissions = Commission.find([('is_prepayment', '=', True)],
    order=[('create_date', 'ASC')])
# commission explanation
# -300 : 12months * 60 - 7months*60
# -150 : 12months * 30 - 7months*60
# 360 : 12months * 30
# 720 : 12months * 60
# base amount: -500: (12 - 7) * 100
[(x.amount, x.base_amount, x.agent.party.name) for x in commissions] == [
    (Decimal('360.00000000'), Decimal('1200.0000'), 'Insurer'),
    (Decimal('720.00000000'), Decimal('1200.0000'), 'Broker'),
    (Decimal('-300.00000000'), Decimal('-500.0000'), 'Broker'),
    (Decimal('-150.00000000'), Decimal('-500.0000'), 'Insurer')]
# #Res# #True

# #Comment# #Reactivate Contract
Wizard('contract.reactivate', models=[contract]).execute('reactivate')
commissions = Commission.find([('is_prepayment', '=', True)],
    order=[('create_date', 'ASC')])
[(x.amount, x.base_amount, x.agent.party.name) for x in commissions] == [
    (Decimal('360.00000000'), Decimal('1200.0000'), 'Insurer'),
    (Decimal('720.00000000'), Decimal('1200.0000'), 'Broker'),
    (Decimal('-300.00000000'), Decimal('-500.0000'), 'Broker'),
    (Decimal('-150.00000000'), Decimal('-500.0000'), 'Insurer'),
    (Decimal('300.00000000'), Decimal('500.0000'), 'Broker'),
    (Decimal('150.00000000'), Decimal('500.0000'), 'Insurer')]
# #Res# #True

# #Comment# #Add new premium version
new_premium_date = contract_start_date + relativedelta(months=9, days=-1)
Account = Model.get('account.account')
ContractPremium = Model.get('contract.premium')
ContractOption = Model.get('contract.option')
Coverage = Model.get('offered.option.description')
contract = Contract(contract.id)
contract.options[0].premiums[0].end = contract_start_date + \
    relativedelta(months=9, days=-1)
contract.options[0].premiums[0].save()
option = ContractOption(contract.options[0].id)
option.premiums.append(ContractPremium(
        start=contract_start_date + relativedelta(months=9),
        amount=Decimal('110'), frequency='monthly',
        account=Account(accounts['revenue'].id),
        rated_entity=Coverage(coverage)))
option.save()
contract.save()

contract.options[0].coverage.premium_rules[0].rule_extra_data = \
    {'premium_amount': Decimal(110)}
contract.options[0].coverage.premium_rules[0].save()

# #Comment# #Invoice contract and post
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')

for contract_invoice in contract.invoices[::-1]:
    if contract_invoice.invoice.state == 'validated':
        contract_invoice.invoice.click('post')

# #Comment# #Check invoice amount and commission
Invoice = Model.get('account.invoice')
last_year_invoice, = Invoice.find([
        ('start', '=', datetime.date(2015, 12, 1)),
        ('state', '=', 'posted')
        ])
last_year_invoice.total_amount
# #Res# #Decimal('110.00')
# commission explanation
# 18 : (12 -9)*(110-100)*0.6
# 48 : (110*0.6)-18
# 9 : (12 -9)*(110-100)*0.3
# 24 : (110*0.3)-9
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in last_year_invoice.lines[0].commissions] == [
    (Decimal('18.0000'), False, Decimal('48.0000'), Decimal('110.0000'),
        'Broker'),
    (Decimal('9.0000'), False, Decimal('24.0000'), Decimal('110.0000'),
        'Insurer')]
# #Res# #True
last_invoice, = Invoice.find([
        ('start', '=', datetime.date(2016, 1, 1)),
        ('state', '=', 'posted')
        ])
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in last_invoice.lines[0].commissions] == [
    (Decimal('66.0000'), False, Decimal('0.0000'), Decimal('110.0000'),
        'Broker'),
    (Decimal('33.0000'), False, Decimal('0.0000'), Decimal('110.0000'),
        'Insurer')]
# #Res# #True

# #Comment# #Terminate Contract
end_date = contract_start_date + relativedelta(months=11, days=-1)
config._context['client_defined_date'] = end_date + relativedelta(days=1)
end_contract = Wizard('contract.stop', models=[contract])
end_contract.form.status = 'terminated'
end_contract.form.at_date = end_date
end_contract.form.sub_status = sub_status
end_contract.execute('stop')

# #Comment# #Check commission once terminated
commissions = Commission.find([('is_prepayment', '=', True)])
# commission explanation
# -48 : 12*100*0.6 - (11-9)*110*0.6 - 9 *100 *0.6
# -24 : 12*100*0.3 - (11-9)*110*0.3 - 9 *100 *0.3
# base amount: -80: (12-11)*100 - (11 - 9)*(110-100)
sorted([(x.amount, x.base_amount, x.agent.party.name) for x in commissions]) \
    == [
    (Decimal('-300.00000000'), Decimal('-500.0000'), 'Broker'),
    (Decimal('-150.00000000'), Decimal('-500.0000'), 'Insurer'),
    (Decimal('-48.00000000'), Decimal('-80.0000'), 'Broker'),
    (Decimal('-24.00000000'), Decimal('-80.0000'), 'Insurer'),
    (Decimal('150.00000000'), Decimal('500.0000'), 'Insurer'),
    (Decimal('300.00000000'), Decimal('500.0000'), 'Broker'),
    (Decimal('360.00000000'), Decimal('1200.0000'), 'Insurer'),
    (Decimal('720.00000000'), Decimal('1200.0000'), 'Broker')]
# #Res# #True
