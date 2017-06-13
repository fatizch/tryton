# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Life Endorsement Scenario
# #Comment# #Imports
import datetime
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from decimal import Decimal

# Useful for updating the tests without having to recreate a db from scratch
# import os
# config = config.set_trytond(
#     database='postgresql://tryton:tryton@localhost:5432/test_db',
#     user='admin',
#     language='en',
#     config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
#         'conf', 'trytond.conf'))
# config.pool.test = True

# #Comment# #Install Modules
config = activate_modules('endorsement_life')

# #Comment# #Get Models
Account = Model.get('account.account')
AccountKind = Model.get('account.account.type')
Clause = Model.get('clause')
Company = Model.get('company.company')
Contract = Model.get('contract')
Country = Model.get('country.country')
CoveredElement = Model.get('contract.covered_element')
Currency = Model.get('currency.currency')
CurrencyRate = Model.get('currency.currency.rate')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')
EndorsementPart = Model.get('endorsement.part')
Field = Model.get('ir.model.field')
FiscalYear = Model.get('account.fiscalyear')
ItemDescription = Model.get('offered.item.description')
Party = Model.get('party.party')
Option = Model.get('contract.option')
OptionDescription = Model.get('offered.option.description')
Product = Model.get('offered.product')
Sequence = Model.get('ir.sequence')
SequenceType = Model.get('ir.sequence.type')
User = Model.get('res.user')
Insurer = Model.get('insurer')

# #Comment# #Constants
today = datetime.date.today()
product_start_date = datetime.date(2014, 1, 1)
contract_start_date = datetime.date(2014, 4, 10)

# #Comment# #Create or fetch Currency
currency, = Currency.find()
CurrencyRate(date=product_start_date, rate=Decimal('1.0'),
    currency=currency).save()

# #Comment# #Create or fetch Country
countries = Country.find([('code', '=', 'FR')])
if not countries:
    country = Country(name='France', code='FR')
    country.save()
else:
    country, = countries

# #Comment# #Create Company
company_config = Wizard('company.company.config')
company_config.execute('company')
company = company_config.form
party = Party(name='World Company')
party.save()
company.party = party
company.currency = currency
company_config.execute('add')
company, = Company.find([])
user = User(1)
user.main_company = company
user.company = company
user.save()

# #Comment# #Reload the context
config._context = User.get_preferences(True, config.context)
config._context['company'] = company.id

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

# #Comment# #Create Beneficiary Clauses
clause1 = Clause()
clause1.name = 'Beneficiary Clause 1'
clause1.content = 'Beneficiary Clause 1 contents'
clause1.kind = 'beneficiary'
clause1.save()
clause2 = Clause()
clause2.name = 'Beneficiary Clause 2'
clause2.content = 'Beneficiary Clause 2 contents'
clause2.kind = 'beneficiary'
clause2.customizable = True
clause2.save()

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
insurer.party.account_receivable = receivable_account
insurer.party.account_payable = payable_account
insurer.party.save()
insurer.save()

# #Comment# #Create Coverage
coverage = OptionDescription()
coverage.company = company
coverage.name = 'Test Coverage'
coverage.code = 'test_coverage'
coverage.family = 'life'
coverage.inurance_kind = 'death'
coverage.start_date = product_start_date
coverage.item_desc = item_description
coverage.insurer = insurer
coverage.beneficiaries_clauses.append(clause1)
coverage.beneficiaries_clauses.append(clause2)
coverage.save()

# #Comment# #Create Product
sequence_code = SequenceType()
sequence_code.name = 'Product sequence'
sequence_code.code = 'contract'
sequence_code.company = company
sequence_code.save()
contract_sequence = Sequence()
contract_sequence.name = 'Contract Sequence'
contract_sequence.code = sequence_code.code
contract_sequence.company = company
contract_sequence.save()
quote_sequence_code = SequenceType()
quote_sequence_code.name = 'Product sequence'
quote_sequence_code.code = 'quote'
quote_sequence_code.company = company
quote_sequence_code.save()
quote_sequence = Sequence()
quote_sequence.name = 'Quote Sequence'
quote_sequence.code = quote_sequence_code.code
quote_sequence.company = company
quote_sequence.save()
product = Product()
product.company = company
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.start_date = product_start_date
product.coverages.append(coverage)
product.save()

# #Comment# #Create Change Beneficiaries
change_beneficiaries_part = EndorsementPart()
change_beneficiaries_part.name = 'Change Beneficiaries'
change_beneficiaries_part.code = 'change_beneficiaries'
change_beneficiaries_part.kind = 'option'
change_beneficiaries_part.view = 'manage_beneficiaries'
endorsed_fields = Field.find([
        ('model.model', '=', 'contract.option'),
        ('name', 'in', ('has_beneficiary_clause', 'beneficiary_clause'))])
for field in endorsed_fields:
    endorsed_field = change_beneficiaries_part.option_fields.new()
    endorsed_field.field = field
endorsed_fields = Field.find([
        ('model.model', '=', 'contract.option'),
        ('name', 'in',
            ('accepting', 'address', 'party', 'reference', 'share'))])
for field in endorsed_fields:
    endorsed_field = change_beneficiaries_part.beneficiary_fields.new()
    endorsed_field.field = field
change_beneficiaries_part.save()
change_beneficiaries = EndorsementDefinition()
change_beneficiaries.name = 'Change Beneficiaries'
change_beneficiaries.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(
        endorsement_part=change_beneficiaries_part))
change_beneficiaries.save()

# #Comment# #Create Subscriber
subscriber = Party()
subscriber.name = 'Doe'
subscriber.first_name = 'John'
subscriber.is_person = True
subscriber.gender = 'male'
subscriber.account_receivable = receivable_account
subscriber.account_payable = payable_account
subscriber.birth_date = datetime.date(1980, 10, 14)
subscriber.save()

# #Comment# #Create Test Contract
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.status = 'active'
contract.contract_number = '123456'
covered_element = contract.covered_elements.new()
covered_element.party = subscriber
option = covered_element.options[0]
option.coverage = coverage
option.has_beneficiary_clause is True
# #Res# #True
option.beneficiary_clause = clause1
beneficiary = option.beneficiaries.new()
beneficiary.accepting = False
beneficiary.reference = 'The girl next door'
contract.end_date = datetime.date(2030, 12, 1)
contract.save()

# #Comment# #New Endorsement
new_payment_date = datetime.date(2014, 7, 1)
new_end_date = datetime.date(2031, 1, 31)
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = change_beneficiaries
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = contract_start_date
new_endorsement.execute('start_endorsement')
new_option = new_endorsement.form.options[0].new_option[0]
# Test disabled because of a proteus bug
# new_option.beneficiary_clause == clause1
# # #Res# #True
new_option.beneficiary_clause = clause2
len(new_option.beneficiaries) == 1
# #Res# #True
new_option.beneficiaries[0].reference += ' and her cat'
new_beneficiary = new_option.beneficiaries.new()
new_beneficiary.accepting = True
new_beneficiary.party = subscriber
new_beneficiary.address = subscriber.addresses[0]
new_endorsement.execute('manage_beneficiaries_next')
new_endorsement.execute('apply_endorsement')

# #Comment# #Test result
contract = Contract(contract.id)
option = contract.covered_elements[0].options[0]
len(option.beneficiaries) == 2
# #Res# #True
option.beneficiaries[0].reference == 'The girl next door and her cat'
# #Res# #True
option.beneficiary_clause == clause2
# #Res# #True
