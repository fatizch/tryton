# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Comment# # Init
import datetime
from decimal import Decimal
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from dateutil.relativedelta import relativedelta

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

config = activate_modules('underwriting_claim_indemnification')

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
template.products[0].code = 'benefit_product'
template.save()
account_product = template.products[0]

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

# #Comment# #Create Insurer
Insurer = Model.get('insurer')
Party = Model.get('party.party')
Account = Model.get('account.account')
insurer = Insurer()
insurer.party = Party()
insurer.party.name = 'Insurer'
insurer.party.account_receivable = Account(accounts['receivable'].id)
insurer.party.account_payable = Account(accounts['payable'].id)
insurer.party.save()
insurer.save()

# #Comment# #Create Product
product = init_product(start_date=datetime.date(2009, 3, 15))
product = add_quote_number_generator(product)
for coverage in product.coverages:
    coverage.insurer = Insurer(insurer.id)
    coverage.save()
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
benefit.insurer = Insurer(insurer.id)
benefit.automatically_deliver = True
benefit.save()

product.coverages[0].benefits.append(benefit)
product.save()

PaybackReason = Model.get('claim.indemnification.payback_reason')
payback_reason = PaybackReason()
payback_reason.code = 'payback_reason'
payback_reason.name = 'Payback Reason'
payback_reason.save()

# create underwriting configuration

UnderwritingDecisionType = Model.get('underwriting.decision.type')
block_decision = UnderwritingDecisionType()
block_decision.name = 'block it'
block_decision.code = 'block it'
block_decision.decision = 'block_indemnification'
block_decision.model = 'claim.service'
block_decision.save()

UnderwritingDecisionType = Model.get('underwriting.decision.type')
reduce_decision = UnderwritingDecisionType()
reduce_decision.name = 'reduce it'
reduce_decision.code = 'reduce it'
reduce_decision.decision = 'reduce_indemnification'
reduce_decision.model = 'claim.service'
reduce_decision.save()

UnderwritingDecisionType = Model.get('underwriting.decision.type')
nothing_decision = UnderwritingDecisionType()
nothing_decision.name = 'nothing'
nothing_decision.code = 'nothing'
nothing_decision.decision = 'nothing'
nothing_decision.model = 'claim.service'
nothing_decision.save()

UnderwritingType = Model.get('underwriting.type')
test_underwriting_control = UnderwritingType(
    name='test_underwriting control',
    code='test_underwriting control',
    )
test_underwriting_control.decisions.append(block_decision)
test_underwriting_control.decisions.append(reduce_decision)
test_underwriting_control.decisions.append(nothing_decision)
test_underwriting_control.provisional_decision = UnderwritingDecisionType(
    block_decision.id)
test_underwriting_control.final_decision = UnderwritingDecisionType(
    reduce_decision.id)
test_underwriting_control.save()

assert test_underwriting_control.provisional_decision.id == block_decision.id
assert test_underwriting_control.final_decision.id == reduce_decision.id

Rule = Model.get('rule_engine')
RuleContext = Model.get('rule_engine.context')
test_underwriting_rule = Rule()
test_underwriting_rule.name = 'test_underwriting Rule'
test_underwriting_rule.short_name = 'test_underwriting_rule'
test_underwriting_rule.algorithm = '\n'.join([
    "date = date_de_debut_du_prejudice()",
    "date = ajouter_jours(date, 46)",
    "return 'test_underwriting control', date"])
test_underwriting_rule.status = 'validated'
test_underwriting_rule.type_ = 'underwriting_type'
test_underwriting_rule.context, = RuleContext.find(
    [('name', '=', 'Context par défaut')])
test_underwriting_rule.save()

Benefit = Model.get('benefit')
benefit = Benefit(benefit.id)
benefit.underwriting_rule = test_underwriting_rule
benefit.save()

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


# #Comment# #Case 1 : the final decision is to reduce : we reject
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
loss.start_date = datetime.date(2016, 1, 01)
loss.end_date = datetime.date(2017, 1, 01)
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

Claim.ws_deliver_automatic_benefit([claim.id], config.context)

service = Claim(claim.id).delivered_services[0]

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

start = datetime.date(2016, 1, 1)
end = datetime.date(2016, 8, 1)
create = Wizard('claim.create_indemnification', models=[service])
create.form.start_date = start
create.form.indemnification_date = start
create.form.end_date = end
create.form.extra_data = {}
create.form.service = service
create.form.beneficiary = subscriber

# #Comment# #Create warning to simulate clicking yes
User = Model.get('res.user')
user, = User.find(['login', '=', 'claim_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'must_activate_underwritings_%s' % str(claim.id)
warning.save()

User = Model.get('res.user')
user, = User.find(['login', '=', 'claim_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'blocked_indemnification_split_warning_%s' % str(service.id)
warning.save()

create.execute('calculate')

indemnifications = sorted(service.indemnifications, key=lambda x: x.start_date)

len(indemnifications) == 2
# #Res# #True

assert indemnifications[0].start_date == start
assert indemnifications[0].end_date == start + relativedelta(days=45)
assert indemnifications[1].start_date == start + relativedelta(days=46)
assert indemnifications[1].end_date == end

indemnifications[0].journal == journal
# #Res# #True

indemnifications[0].click('schedule')
indemnifications[0].status == 'scheduled'
# #Res# #True

indemnifications[1].click('schedule')  # doctest: +IGNORE_EXCEPTION_DETAIL
# #Hard# #Traceback (most recent call last):
# #Hard# #    ...
# #Hard# #UserError: ...

assert 'block it' in indemnifications[1].rec_name

Underwriting = Model.get('underwriting')

processing_underwriting = Underwriting.find([])[0]
assert processing_underwriting.state == 'processing'

result, = processing_underwriting.results
UnderwritingDecisionType = Model.get('underwriting.decision.type')
result.final_decision = UnderwritingDecisionType(reduce_decision.id)
values, = result.click('finalize')
for k, val in values.iteritems():
    setattr(result, k, val)

# #Comment# #Create warning to simulate clicking yes
User = Model.get('res.user')
user, = User.find(['login', '=', 'claim_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'will_reject_%s' % str(indemnifications[1].id)
warning.save()

result.save()
assert result.state == 'finalized', result.state

Indemnification = Model.get('claim.indemnification')
indemnification = Indemnification(indemnifications[1].id)
assert indemnification.status == 'rejected', indemnification.status

config = switch_user('underwriting_user')

Underwriting = Model.get('underwriting')

processing_underwriting = Underwriting.find([])[0]
processing_underwriting.click('complete')

# todo : create a task ("reprise du dossier)

# #Comment# #Case 2 : the final decision is to do nothing special:: we schedule
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
loss.start_date = datetime.date(2016, 1, 01)
loss.end_date = datetime.date(2017, 1, 01)
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

Claim.ws_deliver_automatic_benefit([claim.id], config.context)

service = Claim(claim.id).delivered_services[0]

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

start = datetime.date(2016, 1, 1)
end = datetime.date(2016, 8, 1)
create = Wizard('claim.create_indemnification', models=[service])
create.form.start_date = start
create.form.indemnification_date = start
create.form.end_date = end
create.form.extra_data = {}
create.form.service = service
create.form.beneficiary = subscriber

# #Comment# #Create warning to simulate clicking yes
User = Model.get('res.user')
user, = User.find(['login', '=', 'claim_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'must_activate_underwritings_%s' % str(claim.id)
warning.save()

User = Model.get('res.user')
user, = User.find(['login', '=', 'claim_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'blocked_indemnification_split_warning_%s' % str(service.id)
warning.save()

create.execute('calculate')

indemnifications = sorted(service.indemnifications, key=lambda x: x.start_date)

len(indemnifications) == 2
# #Res# #True

assert indemnifications[0].start_date == start
assert indemnifications[0].end_date == start + relativedelta(days=45)
assert indemnifications[1].start_date == start + relativedelta(days=46)
assert indemnifications[1].end_date == end

indemnifications[0].journal == journal
# #Res# #True

indemnifications[0].click('schedule')
indemnifications[0].status == 'scheduled'
# #Res# #True

indemnifications[1].click('schedule')  # doctest: +IGNORE_EXCEPTION_DETAIL
# #Hard# #Traceback (most recent call last):
# #Hard# #    ...
# #Hard# #UserError: ...

assert 'block it' in indemnifications[1].rec_name

Underwriting = Model.get('underwriting')

processing_underwriting = Underwriting.find([])[1]
assert processing_underwriting.state == 'processing'

result, = processing_underwriting.results
UnderwritingDecisionType = Model.get('underwriting.decision.type')
result.final_decision = UnderwritingDecisionType(nothing_decision.id)
values, = result.click('finalize')
for k, val in values.iteritems():
    setattr(result, k, val)

# #Comment# #Create warning to simulate clicking yes
User = Model.get('res.user')
user, = User.find(['login', '=', 'claim_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'will_schedule_%s' % str(indemnifications[1].id)
warning.save()

result.save()
assert result.state == 'finalized', result.state

Indemnification = Model.get('claim.indemnification')
indemnification = Indemnification(indemnifications[1].id)
assert indemnification.status == 'scheduled', indemnification.status

config = switch_user('underwriting_user')

Underwriting = Model.get('underwriting')

processing_underwriting = Underwriting.find([])[0]
processing_underwriting.click('complete')
