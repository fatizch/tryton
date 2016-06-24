# #Comment# # Init
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from proteus import config, Model, Wizard

# os.environ['DB_NAME'] = 'tests'
# config = config.set_xmlrpc('http://admin:admin@localhost:8068/tests')

# config = config.set_trytond(
#     database='postgresql://jack:coog@localhost:5432/tests',
#     user='admin',
#     config_file=os.path.join(
#         os.environ['VIRTUAL_ENV'], 'conf', 'trytond.conf')
# )

from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.account.tests.tools import (
    create_fiscalyear, create_chart, get_accounts)
from trytond.modules.account_invoice.tests.tools import (
    set_fiscalyear_invoice_sequences)

config = config.set_trytond()
config.pool.test = True

Module = Model.get('ir.module')
claim_module = Module.find([('name', '=', 'claim_indemnification')])[0]
claim_module.click('install')
Wizard('ir.module.install_upgrade').execute('upgrade')

_ = create_country()

currency = get_currency(code='EUR')

_ = create_company(currency=currency)
company = get_company()

User = Model.get('res.user')
user = User(1)
user.company = company
user.save()

config._context = User.get_preferences(True, config.context)
config._context['company'] = company.id

# #Comment# #Create Fiscal Year
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(
    company, today=datetime.date(2015, 1, 1)))
fiscalyear.click('create_period')
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(
    company, today=datetime.date(2015, 1, 1) + relativedelta(years=1)))
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

contract_start_date = datetime.date(2012, 1, 1)

Benefit = Model.get('benefit')
benefit = Benefit()
benefit.name = 'Refund'
benefit.code = 'refund'
benefit.start_date = datetime.date(2010, 1, 1)
benefit.indemnification_kind = 'capital'
benefit.beneficiary_kind = 'subscriber'
benefit.account_product = account_product
benefit.loss_descs.append(loss_desc)
benefit.benefit_rules.append(benefit_rule)
benefit.save()

product.coverages[0].benefits.append(benefit)
product.save()

subscriber = create_party_person(company=company)

Contract = Model.get('contract')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

Claim = Model.get('claim')
claim = Claim()
claim.company = company
claim.declaration_date = datetime.date.today()
claim.claimant = subscriber
claim.main_contract = contract
claim.save()

loss = claim.losses.new()
loss.start_date = datetime.date(2016, 05, 01)
loss.end_date = datetime.date(2017, 01, 01)
loss.loss_desc = loss_desc
loss.event_desc = event_desc
loss.save()

len(claim.losses) == 1
# #Res# #True

ClaimService = Model.get('claim.service')
service = ClaimService()
service.contract = contract
service.option = contract.options[0]
service.benefit = benefit
service.loss = claim.losses[0]
service.get_covered_person = subscriber
service.save()

ExtraData = Model.get('claim.service.extra_data')
data = ExtraData()
data.claim_service = service
data.extra_data_values = {}
data.save()

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
claim_config = Config()
claim_config.control_rule = control_rule
claim_config.save()

# #Comment# #Create indemnifications
create = Wizard('claim.create_indemnification', models=[service])
create.form.start_date = datetime.date(2016, 6, 1)
create.form.end_date = datetime.date(2016, 9, 1)
create.form.extra_data = {}
create.form.service = service
create.execute('calculate')

indemnifications = service.indemnifications
len(indemnifications) > 0
# #Res# #True

indemnifications[0].amount == 3906
# #Res# #True
indemnifications[0].click('schedule')
indemnifications[0].status == 'scheduled'
# #Res# #True

# #Comment# # Get Control Wizard entrypoint
Action = Model.get('ir.action')
action, = Action.find([('name', '=', 'Indemnification Control Wizard')])
action = Action.read([action.id], config.context)[0]

validation = Wizard('claim.indemnification.assistant',
    models=indemnifications, action=action)

validation.form.control[0].action = 'validate'
validation.execute('control_state')

indemnifications[0].control_reason == control_reason
# #Res# #True
indemnifications[0].status == 'controlled'
# #Res# #True

action, = Action.find(['name', '=', 'Indemnification Validation Wizard'])
action = Action.read([action.id], config.context)[0]
validation = Wizard('claim.indemnification.assistant',
    models=indemnifications, action=action)

validation.form.validate[0].action = 'validate'
validation.execute('validation_state')

indemnifications[0].status == 'paid'
# #Res# #True

claim.invoices[0].total_amount == 3906.00
# #Res# #True
