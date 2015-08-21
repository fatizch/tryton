# #Title# #Claim Scenario
# #Comment# #Imports
import datetime
from decimal import Decimal
from proteus import config, Model, Wizard
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.account.tests.tools import create_chart, get_accounts

# #Comment# #Create Database
# config = config.set_trytond()
# config.pool.test = True
# Useful for updating the tests without having to recreate a db from scratch

# config = config.set_xmlrpc('http://admin:admin@localhost:8068/tmp_test')

config = config.set_trytond()
config.pool.test = True

# #Comment# #Install Modules
Module = Model.get('ir.module')
claim_module = Module.find([('name', '=', 'claim')])[0]
claim_module.click('install')
Wizard('ir.module.install_upgrade').execute('upgrade')

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

# #Comment# #Create Product
product = init_product(start_date=datetime.date(2009, 3, 15))
product = add_quote_number_generator(product)
product.save()

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)

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

BenefitRule = Model.get('benefit.rule')
benefit_rule = BenefitRule()
benefit_rule.start_date = datetime.date(2010, 1, 1)
benefit_rule.config_kind = 'simple'
benefit_rule.amount_kind = 'amount'
benefit_rule.amount = Decimal('42')
benefit_rule.offered = product
benefit_rule.save()

Benefit = Model.get('benefit')
benefit = Benefit()
benefit.name = 'Refund'
benefit.code = 'refund'
benefit.start_date = datetime.date(2010, 1, 1)
benefit.indemnification_kind = 'capital'
benefit.beneficiary_kind = 'subscriber'
benefit.loss_descs.append(loss_desc)
benefit.benefit_rules.append(benefit_rule)
benefit.save()

product.coverages[0].benefits.append(benefit)
product.save()


# #Comment# #Create Subscriber
subscriber = create_party_person()

# #Comment# #Create Test Contract
contract_start_date = datetime.date(2012, 1, 1)
Contract = Model.get('contract')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #Create Claim
Claim = Model.get('claim')
claim = Claim()
claim.company = company
claim.declaration_date = datetime.date.today()
claim.claimant = subscriber
claim.company = company
claim.main_contract = contract
claim.save()


# #Comment# #Add Loss
loss = claim.losses.new()
loss.loss_desc = loss_desc
loss.event_desc = event_desc
claim.save()

len(claim.losses) == 1
# #Res# #True

ClaimService = Model.get('claim.service')
service = ClaimService()
service.contract = contract
service.option = contract.options[0]
service.benefit = benefit
service.loss = claim.losses[0]
service.save()

claim.click('button_calculate')

service.status == 'calculated'
# #Res# #True

service.delivered_amount == Decimal('42')
# #Res# #True
