# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Commission Prepayment Scenario Paid Invoice
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

cash = accounts['cash']
receivable = accounts['receivable']
payable = accounts['payable']
Journal = Model.get('account.journal')
expense, = Journal.find([('code', '=', 'EXP')])
cash_journal, = Journal.find([('code', '=', 'CASH')])
cash_journal.debit_account = cash
cash_journal.credit_account = cash
cash_journal.save()

# #Comment# #Create Payment Journal
PaymentJournal = Model.get('account.payment.journal')
payment_journal = PaymentJournal(name='Manual',
    process_method='manual')
payment_journal.save()

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
broker_plan.commission_method = 'payment'
broker_plan.type_ = 'agent'
line = broker_plan.lines.new()
coverage = product.coverages[0].id
line.options.append(Coverage(coverage))
line.formula = 'amount * 0.6'
line.prepayment_formula = 'first_year_premium * 0.6'
broker_plan.save()
broker_plan.prepayment_due_at_first_paid_invoice = True
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
        u'Broker'),
    (Decimal('360.0000'), Decimal('.3'), True, None, Decimal('1200.0000'),
        u'Insurer')]
# #Res# #True

# #Comment# #Create invoices
ContractInvoice = Model.get('contract.invoice')
until_date = contract_start_date + relativedelta(years=1)
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')
contract_invoices = contract.invoices
first_invoice = contract_invoices[0]
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
        u'Broker'),
    (Decimal('0.0000'), False, Decimal('30.0000'), Decimal('100.0000'),
        u'Insurer')]
# #Res# #True

# #Comment# #Validate last invoice of the year commissions
before_last_invoice = contract_invoices[1]
line, = before_last_invoice.invoice.lines
len(line.commissions)
# #Res# #2
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in line.commissions] == [
    (Decimal('0.0000'), False, Decimal('60.0000'), Decimal('100.0000'),
        u'Broker'),
    (Decimal('0.0000'), False, Decimal('30.0000'), Decimal('100.0000'),
        u'Insurer')]
# #Res# #True

# #Comment# #Validate first invoice of next year commissions
last_invoice = contract_invoices[0]
line, = last_invoice.invoice.lines
len(line.commissions)
# #Res# #2
[(x.amount, x.is_prepayment, x.redeemed_prepayment, x.base_amount,
    x.agent.party.name) for x in line.commissions] == [
    (Decimal('60.0000'), False, Decimal('0.0000'), Decimal('100.0000'),
        u'Broker'),
    (Decimal('30.0000'), False, Decimal('0.0000'), Decimal('100.0000'),
        u'Insurer')]
# #Res# #True

# #Comment# # Nothing is paid, no broker invoice is generated
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
Invoice = Model.get('account.invoice')
Invoice.find([('business_kind', '=', 'broker_invoice')]) == []
# #Res# #True

# #Comment# # Pay the first invoice
first_account_invoice = first_invoice.invoice
PayInvoice = Wizard('account.invoice.pay', [first_account_invoice])
cash_journal, = Journal.find([('code', '=', 'CASH')])
PayInvoice.form.journal = cash_journal
PayInvoice.form.date = contract.start_date
PayInvoice.execute('choice')

first_account_invoice.reload()
first_account_invoice.state
# #Res# #u'paid'

prepayment_coms = Commission.find([('is_prepayment', '=', True)])
assert all(com.date for com in prepayment_coms)


# #Comment# #Pay and then cancel another invoice,
# #Comment# #make sure the date of commission is untouched
second_invoice = contract_invoices[1]
second_account_invoice = second_invoice.invoice
PayInvoice = Wizard('account.invoice.pay', [second_account_invoice])
cash_journal, = Journal.find([('code', '=', 'CASH')])
PayInvoice.form.journal = cash_journal
PayInvoice.form.date = contract.start_date
PayInvoice.execute('choice')

second_account_invoice.reload()
second_account_invoice.state
# #Res# #u'paid'

second_account_invoice.payment_lines[0].reconciliation.delete()
second_account_invoice.reload()
second_account_invoice.state
# #Res# #u'posted'

prepayment_coms = Commission.find([('is_prepayment', '=', True)])
assert all(com.date for com in prepayment_coms)


# #Comment# #Generate broker invoice
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')


# The prepayment is now included in a new broker_invoice
Invoice = Model.get('account.invoice')
broker_invoice, = Invoice.find([
        ('business_kind', '=', 'broker_invoice')])
sorted([(x.description, x.amount) for x in broker_invoice.lines]) == [
    (u'Prepayment', Decimal('720.00')),
    (u'Prepayment Amortization', Decimal('0.00'))]
# #Res# #True

first_broker_invoice_id = broker_invoice.id

# unpay the first invoice
first_account_invoice.payment_lines[0].reconciliation.delete()
first_account_invoice.reload()
first_account_invoice.state
# #Res# #u'posted'

# #Comment# #Generate broker invoice
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
new_broker_invoice, = Invoice.find([
        ('business_kind', '=', 'broker_invoice'),
        ('id', '!=', first_broker_invoice_id)])
second_broker_invoice_id = new_broker_invoice.id

# The contract invoice is not paid anymore, so we should cancel the
# redeemed prepayment
sorted([(x.description, x.amount) for x in new_broker_invoice.lines]) == [
    (u'Prepayment Amortization', Decimal('0.00'))]
# #Res# #True

coms_in_second_broker_invoice, = Commission.find([('invoice_line.id', '=',
        new_broker_invoice.lines[0].id)])

coms_in_second_broker_invoice.redeemed_prepayment == Decimal('-60.00')
# #Res# #True

# #Comment# #Terminate contrat after two months
end_date = contract_start_date + relativedelta(months=2, days=-1)
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

contract.reload()

# the contract has been reconciled
# we now have one paid invoice, one posted invoice,
# and all the rest is cancelled

contract_invoices = contract.invoices
paid_invoices = [x.invoice for x in contract_invoices
    if x.invoice_state == 'paid']
posted_invoices = [x.invoice for x in contract_invoices if
    x.invoice_state == 'posted']
assert len(paid_invoices) == 1
assert len(posted_invoices) == 1

# #Comment# #Generate broker invoice
create_invoice = Wizard('commission.create_invoice')
create_invoice.form.from_ = None
create_invoice.form.to = None
create_invoice.execute('create_')
third_broker_invoice, = Invoice.find([
        ('business_kind', '=', 'broker_invoice'),
        ('id', 'not in', (first_broker_invoice_id, second_broker_invoice_id))])

# the Broker Plan line is for the second year
# because we had a linear commission, that is now balanced by a new commission
# with negative amount
sorted([(x.description, x.amount) for x in third_broker_invoice.lines]) == [
    (u'Broker Plan', Decimal('0.00')),
    (u'Prepayment', Decimal('-600.00')),
    (u'Prepayment Amortization', Decimal('0.00'))]
# #Res# #True

amort_line, = [x for x in third_broker_invoice.lines
    if x.description == u'Prepayment Amortization']
amort_coms = Commission.find([('invoice_line.id', '=', amort_line.id)])
sum(amort_com.redeemed_prepayment
    for amort_com in amort_coms) == Decimal('60.00')
# #Res# #True

# In the end, the contract lives only two months
# we must reimburse the whole prepayment except for
# those 2 months
prepayment_line, = [x for x in third_broker_invoice.lines
    if x.description == u'Prepayment']
prepayment_com, = Commission.find([
        ('invoice_line.id', '=', prepayment_line.id)])
prepayment_com.amount == Decimal('-600.00')
# #Res# #True

linear_line, = [x for x in third_broker_invoice.lines
    if x.description == u'Broker Plan']
linear_coms = Commission.find([
        ('invoice_line.id', '=', linear_line.id)])
sorted([x.amount for x in linear_coms]) == [
    Decimal('-60.00'), Decimal('60.00')]
# #Res# #True
