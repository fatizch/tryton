# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Comment# # Init
import datetime
from decimal import Decimal
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules

from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.account.tests.tools import (
    create_fiscalyear, create_chart, get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    set_fiscalyear_invoice_sequences)
from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user

config = activate_modules('claim_indemnification')

_ = create_country()
currency = get_currency(code='EUR')
_ = create_company(currency=currency)
company = get_company()

execute_test_case('authorizations_test_case')
config = switch_user('financial_user')
company = get_company()

# #Comment# #Create Fiscal Year
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(
    company, today=datetime.date(datetime.date.today().year, 1, 1)))
fiscalyear.click('create_period')
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(
    company, today=datetime.date(datetime.date.today().year + 1, 1, 1)))
fiscalyear.click('create_period')

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)

# #Comment# #Create benefit account product
Uom = Model.get('product.uom')
Template = Model.get('product.template')
Product = Model.get('product.product')
unit, = Uom.find([('name', '=', 'Unit')])
account_product = Product()
template = Template()
template.name = 'Benefit Product'
template.default_uom = unit
template.type = 'service'
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.account_expense = accounts['expense']
template.account_revenue = accounts['revenue']
template.save()
account_product.template = template
account_product.save()

# #Comment# #Create Payment Journal

Journal = Model.get('account.payment.journal')
currency = get_currency(code='EUR')
journal = Journal()
journal.name = 'Manual Journal'
journal.company = company
journal.currency = currency
journal.process_method = 'manual'
journal.save()

config = switch_user('product_user')
company = get_company()

# #Comment# #Create Product
product = init_product(start_date=datetime.date(2009, 3, 15))
product = add_quote_number_generator(product)
product.save()

# #Comment# #Create Claim Configuration
EventDescriptionLossDescriptionRelation = Model.get(
    'benefit.event.description-loss.description')
LossDesc = Model.get('benefit.loss.description')
loss_desc = LossDesc()
loss_desc.code = 'disability'
loss_desc.name = 'Disability'
loss_desc.company = company
loss_desc.loss_kind = 'generic'
loss_desc.save()

EventDesc = Model.get('benefit.event.description')
event_desc = EventDesc()
event_desc.code = 'accident'
event_desc.name = 'Accident'
event_desc.loss_descs.append(LossDesc(loss_desc.id))
event_desc.save()

Rule = Model.get('rule_engine')
BenefitRule = Model.get('benefit.rule')
benefit_rule = BenefitRule()
benefit_rule.indemnification_rule_extra_data = {}
benefit_rule.indemnification_rule, = Rule.find([
        ('short_name', '=', 'simple_claim_rule')])
benefit_rule.indemnification_rule_extra_data = {'claim_amount': Decimal('42')}
benefit_rule.offered = product

RuleContext = Model.get('rule_engine.context')
ControlRule = Model.get('claim.indemnification.control.rule')
control_rule = ControlRule()
rule = Rule()
rule.type_ = 'benefit'
rule.short_name = 'claim_control_rule'
rule.name = 'Claim Control Rule'
control_reason = "Amount is large"
rule.algorithm = "return (True, '%s')" % control_reason
rule.status = 'validated'
rule.context = RuleContext(1)
rule.save()
control_rule.rule = rule
control_rule.save()

PaymentTerm = Model.get('account.invoice.payment_term')
PaymentTermLine = Model.get('account.invoice.payment_term.line')
payment_term = PaymentTerm()
payment_term.name = 'test'
payment_term.lines.append(PaymentTermLine())
payment_term.save()

Config = Model.get('claim.configuration')
Journal = Model.get('account.payment.journal')
journal = Journal(journal.id)
claim_config = Config()
claim_config.control_rule = control_rule
claim_config.payment_journal = journal
claim_config.claim_default_payment_term = payment_term
claim_config.save()

Benefit = Model.get('benefit')
Product = Model.get('product.product')
benefit = Benefit()
account_product = Product(account_product.id)
benefit.name = 'Refund'
benefit.code = 'refund'
benefit.start_date = datetime.date(2010, 1, 1)
benefit.indemnification_kind = 'capital'
benefit.beneficiary_kind = 'subscriber'
benefit.products.append(account_product)
benefit.loss_descs.append(LossDesc(loss_desc.id))
benefit.benefit_rules.append(benefit_rule)
benefit.save()

product.coverages[0].benefits.append(benefit)
product.save()


config = switch_user('contract_user')
company = get_company()
accounts = get_accounts(company)
Party = Model.get('party.party')
Account = Model.get('account.account')

subscriber = Party()
subscriber.name = 'Doe'
subscriber.first_name = 'John'
subscriber.is_person = True
subscriber.gender = 'male'
subscriber.account_receivable = Account(accounts['receivable'].id)
subscriber.account_payable = Account(accounts['payable'].id)
subscriber.birth_date = datetime.date(1980, 10, 14)
subscriber.save()

Contract = Model.get('contract')
product = Model.get('offered.product')(product.id)

contract_start_date = datetime.date(2012, 1, 1)
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

config = switch_user('claim_user')
company = get_company()

Claim = Model.get('claim')
Contract = Model.get('contract')
Party = Model.get('party.party')
claim = Claim()
claim.company = company
claim.declaration_date = datetime.date.today()
claim.claimant = Party(subscriber.id)
claim.main_contract = Contract(contract.id)
claim.save()

EventDesc = Model.get('benefit.event.description')
LossDesc = Model.get('benefit.loss.description')
event_desc = EventDesc(event_desc.id)
loss_desc = LossDesc(loss_desc.id)

loss = claim.losses.new()
loss.start_date = datetime.date(2016, 01, 01)
loss.end_date = datetime.date(2017, 01, 01)
loss.loss_desc = loss_desc
loss.event_desc = event_desc
loss.save()
loss.click('activate')

len(claim.losses) == 1
# #Res# #True

ClaimService = Model.get('claim.service')
Benefit = Model.get('benefit')
Party = Model.get('party.party')

subscriber = Party(subscriber.id)
benefit = Benefit(benefit.id)

Contract = Model.get('contract')
service = ClaimService()
service.contract = Contract(contract.id)
service.option = Contract(contract.id).options[0]
service.benefit = benefit
service.loss = claim.losses[0]
service.get_covered_person = subscriber
service.save()

ExtraData = Model.get('claim.service.extra_data')
data = ExtraData()
data.claim_service = service
data.extra_data_values = {}
data.save()


Action = Model.get('ir.action')
action, = Action.find(['name', '=', 'Indemnification Validation Wizard'])
validate_action = Action.read([action.id], config.context)[0]

action, = Action.find(['name', '=', 'Indemnification Control Wizard'])
control_action = Action.read([action.id], config.context)[0]

# #Comment# #Create indemnifications
ClaimService = Model.get('claim.service')
Party = Model.get('party.party')
service = ClaimService(service.id)
subscriber = Party(subscriber.id)

create = Wizard('claim.create_indemnification', models=[service])
create.form.start_date = datetime.date(2016, 1, 1)
create.form.indemnification_date = datetime.date(2016, 1, 1)
create.form.end_date = datetime.date(2016, 8, 1)
create.form.extra_data = {}
create.form.service = service
create.form.beneficiary = subscriber
create.execute('calculate')

indemnifications = service.indemnifications

len(indemnifications) == 1
# #Res# #True

indemnifications[0].amount == 8988
# #Res# #True


indemnifications[0].journal == journal
# #Res# #True

indemnifications[0].click('schedule')
indemnifications[0].status == 'scheduled'
# #Res# #True

controller = Wizard('claim.indemnification.assistant',
    models=indemnifications,
    action=control_action)

# #Comment# # Manually set wizard mode for apply_filters
controller.form.mode = 'control'
controller.form.order_sort = 'ASC'
controller.form.control[0].action = 'validate'
controller.execute('control_state')

indemnifications[0].status == 'controlled'
# #Res# #True

validator = Wizard('claim.indemnification.assistant',
    models=indemnifications, action=validate_action)

validator.form.validate[0].action = 'validate'
validator.execute('validation_state')

# #Comment# #Create warning to simulate clicking yes
User = Model.get('res.user')
user, = User.find(['login', '=', 'claim_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'overlap_date'
warning.save()

# #Comment# #Generate Regularisation
create = Wizard('claim.create_indemnification', models=[service])
create.form.start_date = datetime.date(2016, 1, 1)
create.form.indemnification_date = datetime.date(2016, 1, 1)
create.form.end_date = datetime.date(2016, 6, 1)
create.form.extra_data = {}
create.form.service = service
create.form.beneficiary = subscriber

# First call will raise a Warning
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'multiple_capital_indemnifications_[1]'
warning.save()
create.execute('calculate')
create.execute('regularisation')
create.form.payback_method = 'planned'
create.execute('apply_regularisation')

indemnifications = service.indemnifications

len(indemnifications) == 2
# #Res# #True

# #Comment# #Schedule the indemnification
indemnifications[1].click('schedule')
indemnifications[0].click('schedule')

indemnifications[0].status == 'scheduled'
# #Res# #True

indemnifications[1].status == 'cancel_scheduled'
# #Res# #True

controller = Wizard('claim.indemnification.assistant',
    models=indemnifications, action=control_action)

controller.form.mode = 'control'
controller.form.order_sort = 'ASC'
controller.form.control[0].action = 'validate'
controller.form.control[1].action = 'validate'
controller.execute('control_state')

indemnifications[1].status == 'cancel_controlled'
# #Res# #True
indemnifications[0].control_reason == control_reason
# #Res# #True
indemnifications[0].status == 'controlled'
# #Res# #True

validator = Wizard('claim.indemnification.assistant',
    models=indemnifications, action=validate_action)

len(validator.form.validate) == 2
# #Res# #True

validator.form.validate[0].action = 'validate'
validator.form.validate[1].action = 'validate'
validator.execute('validation_state')

indemnifications[1].status == 'cancel_paid'
# #Res# #True

indemnifications[0].status == 'paid'
# #Res# #True

claim.invoices[0].total_amount < 0
# #Res# #True
