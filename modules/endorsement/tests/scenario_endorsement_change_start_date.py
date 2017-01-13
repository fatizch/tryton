# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Start Date Endorsement Scenario
# #Comment# #Imports
import datetime
from proteus import config, Model, Wizard
from dateutil.relativedelta import relativedelta
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency

# Useful for updating the tests without having to recreate a db from scratch
# import os
# config = config.set_trytond(
#     database='postgresql://tryton:tryton@localhost:5432/test_db',
#     user='admin',
#     language='en',
#     config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
#         'conf', 'trytond.conf'))

# #Comment# #Install Modules
config = activate_modules('endorsement')

# #Comment# #Get Models
Company = Model.get('company.company')
Contract = Model.get('contract')
Country = Model.get('country.country')
Endorsement = Model.get('endorsement')
EndorsementContract = Model.get('endorsement.contract')
EndorsementContractField = Model.get('endorsement.contract.field')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')
EndorsementPart = Model.get('endorsement.part')
Field = Model.get('ir.model.field')
MethodDefinition = Model.get('ir.model.method')
Option = Model.get('contract.option')
OptionDescription = Model.get('offered.option.description')
Party = Model.get('party.party')
Product = Model.get('offered.product')
Sequence = Model.get('ir.sequence')
SequenceType = Model.get('ir.sequence.type')
User = Model.get('res.user')

# #Comment# #Constants
today = datetime.date.today()
product_start_date = datetime.date(2014, 1, 1)
contract_start_date = datetime.date(2014, 4, 10)
new_contract_start_date = datetime.date(2014, 10, 21)

# #Comment# #Create or fetch Currency
currency = get_currency(code='EUR')

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
coverage = OptionDescription()
coverage.company = company
coverage.currency = currency
coverage.name = 'Test Coverage'
coverage.code = 'test_coverage'
coverage.start_date = product_start_date
coverage.save()
product = Product()
product.company = company
product.currency = currency
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.start_date = product_start_date
product.coverages.append(coverage)
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

# #Comment# #Create Void Endorsement
void_contract_part = EndorsementPart()
void_contract_part.name = 'Change Start Date'
void_contract_part.code = 'void_contract'
void_contract_part.kind = 'contract'
void_contract_part.view = 'void_contract'
void_contract_part.save()
void_contract = EndorsementDefinition()
void_contract.name = 'Void Contract'
void_contract.code = 'void_contract'
void_contract.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(endorsement_part=void_contract_part))
void_contract.save()

# #Comment# #Create Terminate Endorsement
terminate_contract_part = EndorsementPart()
terminate_contract_part.name = 'Change Start Date'
terminate_contract_part.code = 'terminate_contract'
terminate_contract_part.kind = 'contract'
terminate_contract_part.view = 'terminate_contract'
terminate_contract_part.save()
terminate_contract = EndorsementDefinition()
terminate_contract.name = 'Terminate Contract'
terminate_contract.code = 'teminate_contract'
terminate_contract.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(
        endorsement_part=terminate_contract_part))
terminate_contract.save()

# #Comment# #Create Test Contract
contract = Contract()
contract.company = company
contract.start_date = contract_start_date
contract.product = product
contract.contract_number = '1111'
contract.status = 'active'
contract.save()

# #Comment# #New Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = change_start_date
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
# #Comment# # Check endorsement was properly created
good_endorsement, = Endorsement.find([
        ('contracts', '=', contract.id)])
contract = Contract(contract.id)
contract.start_date == contract_start_date
# #Res# #True
contract.options[0].start_date == contract_start_date
# #Res# #True
_ = Endorsement.apply([good_endorsement.id], config._context)
contract = Contract(contract.id)
contract.start_date == new_contract_start_date
# #Res# #True
contract.options[0].start_date == new_contract_start_date
# #Res# #True
Endorsement.cancel([good_endorsement.id], config._context)
contract = Contract(contract.id)
contract.start_date == contract_start_date
# #Res# #True
contract.options[0].start_date == contract_start_date
# #Res# #True

# #Comment# #Test options restauration
good_endorsement.state = 'draft'
good_endorsement.save()
_ = Endorsement.apply([good_endorsement.id], config._context)
contract = Contract(contract.id)
Option.delete([contract.options[0]])
contract = Contract(contract.id)
len(contract.options) == 0
# #Res# #True
Endorsement.cancel([good_endorsement.id], config._context)
contract = Contract(contract.id)
len(contract.options) == 1
# #Res# #True

# #Comment# #Test Terminate Endorsement
SubStatus = Model.get('contract.sub_status')
terminated_status, = SubStatus.find([('code', '=', 'terminated')])
# #Comment# #New Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = terminate_contract
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = contract_start_date + \
    relativedelta(months=3)
new_endorsement.execute('start_endorsement')
new_endorsement.form.termination_reason = terminated_status
new_endorsement.execute('terminate_contract_next')
new_endorsement.execute('apply_endorsement')

contract = Contract(contract.id)
contract.start_date == contract_start_date
# #Res# #True
contract.initial_start_date == contract_start_date
# #Res# #True
contract.status == 'terminated'
# #Res# #True
contract.end_date == contract_start_date + relativedelta(months=3)
# #Res# #True
contract.termination_reason == terminated_status
# #Res# #True

good_endorsement, = Endorsement.find([
        ('contracts', '=', contract.id),
        ('state', '=', 'applied')])
Endorsement.cancel([good_endorsement.id], config._context)
contract = Contract(contract.id)

contract.start_date == contract_start_date
# #Res# #True
contract.end_date == None
# #Res# #True
contract.termination_reason == None
# #Res# #True


# #Comment# #Test Void Endorsement
SubStatus = Model.get('contract.sub_status')
error, = SubStatus.find([('code', '=', 'error')])
# #Comment# #New Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = void_contract
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = contract_start_date
new_endorsement.execute('start_endorsement')
new_endorsement.form.void_reason = error
new_endorsement.execute('void_contract_next')
new_endorsement.execute('apply_endorsement')

contract = Contract(contract.id)
contract.start_date == None
# #Res# #True
contract.initial_start_date == contract_start_date
# #Res# #True
contract.status == 'void'
# #Res# #True
contract.sub_status == error
# #Res# #True
