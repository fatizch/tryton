# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Renew Contract Scenario
# #Comment# #Imports
import datetime
from proteus import Model, Wizard
from dateutil.relativedelta import relativedelta
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import get_company
from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user

# Useful for updating the tests without having to recreate a db from scratch
# import os
# config = config.set_trytond(
#    database='postgresql://tryton:tryton@localhost:5432/test_db_22',
#    user='admin',
#    config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
#        'conf', 'trytond.conf'))


# #Comment# #Install Modules
config = activate_modules(['contract_term_renewal', 'endorsement'])

# #Comment# #Constants
today = datetime.date.today()
contract_start_date = datetime.date(2013, 4, 10)
product_start_date = datetime.date(2013, 1, 1)

# #Comment# #Get Models
Country = Model.get('country.country')
# #Comment# #Create or fetch Currency
currency = get_currency(code='EUR')

# #Comment# #Create or fetch Country
countries = Country.find([('code', '=', 'FR')])
if not countries:
    country = Country(name='France', code='FR')
    country.save()
else:
    country, = countries


# #Comment# #Get Models
Company = Model.get('company.company')
Party = Model.get('party.party')
User = Model.get('res.user')
AccountKind = Model.get('account.account.type')
Account = Model.get('account.account')

# #Comment# #Create Company
company_config = Wizard('company.company.config')
company_config.execute('company')
company = company_config.form
party = Party(name='World Company')
party.save()
company.party = party
company.currency = get_currency(code='EUR')
company_config.execute('add')
company, = Company.find([])
user = User(1)
user.main_company = company
user.company = company
user.save()

# #Comment# #Reload the context
config._context = User.get_preferences(True, config.context)
config._context['company'] = company.id

execute_test_case('authorizations_test_case')
config = switch_user('financial_user')

# #Comment# #Create Account Kind
product_account_kind = AccountKind()
product_account_kind.name = 'Product Account Kind'
product_account_kind.company = company
product_account_kind.save()
receivable_account_kind = AccountKind()
receivable_account_kind.name = 'Receivable Account Kind'
receivable_account_kind.company = company
receivable_account_kind.save()
payable_account_kind = AccountKind()
payable_account_kind.name = 'Payable Account Kind'
payable_account_kind.company = company
payable_account_kind.save()

# #Comment# #Create Account
product_account = Account()
product_account.name = 'Product Account'
product_account.code = 'product_account'
product_account.kind = 'revenue'
product_account.type = product_account_kind
product_account.company = company
product_account.save()
receivable_account = Account()
receivable_account.name = 'Account Receivable'
receivable_account.code = 'account_receivable'
receivable_account.kind = 'receivable'
receivable_account.reconcile = True
receivable_account.type = receivable_account_kind
receivable_account.company = company
receivable_account.save()
payable_account = Account()
payable_account.name = 'Account Payable'
payable_account.code = 'account_payable'
payable_account.kind = 'payable'
payable_account.type = payable_account_kind
payable_account.company = company
payable_account.save()

config = switch_user('product_user')

Sequence = Model.get('ir.sequence')
SequenceType = Model.get('ir.sequence.type')
OptionDescription = Model.get('offered.option.description')
Product = Model.get('offered.product')
Rule = Model.get('rule_engine')
Company = get_company()
ItemDescription = Model.get('offered.item.description')
Insurer = Model.get('insurer')
Account = Model.get('account.account')
Party = Model.get('party.party')
EndorsementPart = Model.get('endorsement.part')
Field = Model.get('ir.model.field')
EndorsementContractField = Model.get('endorsement.contract.field')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')

# #Comment# #Create Item Description
item_description = ItemDescription()
item_description.name = 'Test Item Description'
item_description.code = 'test_item_description'
item_description.kind = 'person'
item_description.save()

# #Comment# #Create Insurer
insurer = Insurer()
insurer.party = Party()
insurer.party.name = 'Insurer'
insurer.party.account_receivable = Account(receivable_account.id)
insurer.party.account_payable = Account(payable_account.id)
insurer.party.save()
insurer.save()

# #Comment# #Create Product
sequence_code = SequenceType()
sequence_code.name = 'Product sequence'
sequence_code.code = 'contract'
sequence_code.company = get_company()
sequence_code.save()
contract_sequence = Sequence()
contract_sequence.name = 'Contract Sequence'
contract_sequence.code = sequence_code.code
contract_sequence.company = get_company()
contract_sequence.save()
quote_sequence_code = SequenceType()
quote_sequence_code.name = 'Product sequence'
quote_sequence_code.code = 'quote'
quote_sequence_code.company = get_company()
quote_sequence_code.save()
quote_sequence = Sequence()
quote_sequence.name = 'Quote Sequence'
quote_sequence.code = quote_sequence_code.code
quote_sequence.company = get_company()
quote_sequence.save()
coverage = OptionDescription()
coverage.company = get_company()
coverage.currency = get_currency(code='EUR')
coverage.name = 'Test Coverage'
coverage.code = 'test_coverage'
coverage.start_date = product_start_date
coverage.item_desc = item_description
coverage.insurer = Insurer(insurer.id)
coverage.subscription_behaviour = 'optional'
coverage.save()
product = Product()
product.company = get_company()
product.currency = get_currency(code='EUR')
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.start_date = product_start_date
product.coverages.append(coverage)
product.save()
renewal_rule = product.term_renewal_rule.new()
renewal_rule.allow_renewal = True
subscription_date_sync_rule, = Rule.find([
        ('short_name', '=', 'product_term_renewal_sync_sub_date')])
renewal_rule.rule = subscription_date_sync_rule
renewal_rule.product = product
renewal_rule.save()
product.save()

# #Comment# #Create Change Start Date Endorsement
change_start_date_part = EndorsementPart()
change_start_date_part.name = 'Change Start Date'
change_start_date_part.code = 'change_start_date'
change_start_date_part.kind = 'contract'
change_start_date_part.view = 'change_start_date'
change_start_date_part.contract_fields.append(
    EndorsementContractField(field=Field.find([
                ('model.model', '=', 'contract'),
                ('name', '=', 'start_date')])[0].id))
change_start_date_part.save()
change_start_date = EndorsementDefinition()
change_start_date.name = 'Change Start Date'
change_start_date.code = 'change_start_date'
change_start_date.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(endorsement_part=change_start_date_part))
change_start_date.save()

config = switch_user('contract_user')

Party = Model.get('party.party')
Account = Model.get('account.account')
EndorsementPart = Model.get('endorsement.part')
Field = Model.get('ir.model.field')
EndorsementContractField = Model.get('endorsement.contract.field')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')
Contract = Model.get('contract')
Company = get_company()
Product = Model.get('offered.product')
EndorsementDefinition = Model.get('endorsement.definition')
Endorsement = Model.get('endorsement')

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
contract = Contract()
contract.company = get_company()
contract.start_date = contract_start_date
contract.product = Product(product.id)
contract.subscriber = subscriber
contract.status = 'quote'
contract.save()
activate = Wizard('contract.activate', models=[contract])
activate.execute('apply')
contract.save()


contract.start_date == contract_start_date
# #Res# #True
contract.end_date
# #Res# #datetime.date(2014, 4, 9)

new_contract_start_date = contract_start_date + relativedelta(years=1)

# #Comment# #New Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = EndorsementDefinition(
    change_start_date.id)
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = new_contract_start_date
new_endorsement.execute('start_endorsement')
new_endorsement.form.current_start_date == contract_start_date
# #Res# #True
new_endorsement.form.new_start_date == new_contract_start_date
# #Res# #True
new_endorsement.execute('change_start_date_next')
new_endorsement.execute('suspend')
good_endorsement, = Endorsement.find([
        ('contracts', '=', contract.id)])
_ = Endorsement.apply([good_endorsement.id], config._context)
contract = Contract(contract.id)
contract.start_date == new_contract_start_date
# #Res# #True
contract.end_date == new_contract_start_date + relativedelta(years=1, days=-1)
# #Res# #True


# #Comment# #Cancel Endorsement
Endorsement.cancel([good_endorsement.id], config._context)
contract = Contract(contract.id)
contract.start_date == contract_start_date
# #Res# #True

# #Comment# #Renew Contract
renew = Wizard('contract_term_renewal.renew', models=[contract])
renew.execute('renew')
contract.save()

# #Comment# #Check that new period is correctly created
len(contract.activation_history)
# #Res# #2
contract.activation_history[1].start_date
# #Res# #datetime.date(2014, 4, 10)
contract.activation_history[1].end_date
# #Res# #datetime.date(2015, 4, 9)


config._context['client_defined_date'] = datetime.date(2013, 12, 25)
# #Comment# #Test activation history getter
contract.start_date == contract_start_date
# #Res# #True
contract.end_date
# #Res# #datetime.date(2014, 4, 9)


# #Comment# #Simulate consultation during next activation period
# #Comment# #Clean Cache
contract.save()
config._context['client_defined_date'] = datetime.date(2014, 12, 25)
contract.start_date
# #Res# #datetime.date(2014, 4, 10)
contract.end_date
# #Res# #datetime.date(2015, 4, 9)


# #Comment# #Simulate consultation after last activation period
# #Comment# #Clean Cache
contract.save()
config._context['client_defined_date'] = datetime.date(2018, 12, 25)
contract.start_date
# #Res# #datetime.date(2014, 4, 10)
contract.end_date
# #Res# #datetime.date(2015, 4, 9)

# #Comment# #Simulate consultation before first activation period
# #Comment# #Clean Cache
contract.save()
config._context['client_defined_date'] = datetime.date(2001, 12, 25)
contract.start_date == contract_start_date
# #Res# #True
contract.end_date
# #Res# #datetime.date(2014, 4, 9)
