# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Extra Data Endorsement Scenario
# #Comment# #Imports
import datetime
from proteus import config, Model, Wizard
from trytond.modules.currency.tests.tools import get_currency

# #Comment# #Init Database
config = config.set_trytond()
config.pool.test = True
# Useful for updating the tests without having to recreate a db from scratch
# import os
# config = config.set_trytond(
#     database='postgresql://tryton:tryton@localhost:5432/test_db',
#     user='admin',
#     language='en_US',
#     config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
#         'conf', 'trytond.conf'))

# #Comment# #Install Modules
Module = Model.get('ir.module')
endorsement_module = Module.find([('name', '=', 'endorsement')])[0]
Module.install([endorsement_module.id], config.context)
wizard = Wizard('ir.module.install_upgrade')
wizard.execute('upgrade')

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
ContractExtraData = Model.get('contract.extra_data')
ExtraData = Model.get('extra_data')
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
effective_date = datetime.date(2014, 10, 21)

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

# #Comment# #Create Test ExtraData
extra_data = ExtraData()
extra_data.name = 'formula'
extra_data.code = 'formula'
extra_data.type_ = 'integer'
extra_data.string = 'formula'
extra_data.kind = 'contract'
extra_data.save()

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
product.extra_data_def.append(extra_data)
product.save()

# #Comment# #Create Change Extra Data Endorsement
change_extra_data_part = EndorsementPart()
change_extra_data_part.name = 'Change Extra Data'
change_extra_data_part.code = 'change_extra_data'
change_extra_data_part.kind = 'extra_data'
change_extra_data_part.view = 'change_contract_extra_data'
change_extra_data_part.save()
change_extra_data = EndorsementDefinition()
change_extra_data.name = 'Change Extra Data'
change_extra_data.code = 'change_extra_data'
change_extra_data.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(endorsement_part=change_extra_data_part))
change_extra_data.save()

# #Comment# #Create Test Contract
contract = Contract()
contract.company = company
contract.start_date = contract_start_date
contract.product = product
contract.contract_number = '1111'
contract.status = 'active'
contract.save()

contract.extra_datas[0].extra_data_values = {'formula': 1}
contract.extra_datas[0].date = None
contract.extra_datas[0].save()


len(contract.extra_datas) == 1
# #Res# #True
contract.extra_datas[0].extra_data_values == {'formula': 1}
# #Res# #True


# #Comment# #New Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = change_extra_data
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = effective_date
new_endorsement.execute('start_endorsement')
new_endorsement.form.current_extra_data_date == None
# #Res# #True
new_endorsement.form.new_extra_data_date == effective_date
# #Res# #True
new_endorsement.form.new_extra_data = {'formula': 2}
new_endorsement.execute('change_contract_extra_data_next')
new_endorsement.execute('apply_endorsement')
contract.save()


len(contract.extra_datas) == 2
# #Res# #True
contract.extra_datas[0].extra_data_values == {'formula': 1}
# #Res# #True
contract.extra_datas[0].date == None
# #Res# #True
contract.extra_datas[1].extra_data_values == {'formula': 2}
# #Res# #True
contract.extra_datas[1].date == effective_date
# #Res# #True

good_endorsement, = Endorsement.find([
        ('contracts', '=', contract.id)])
Endorsement.cancel([good_endorsement.id], config._context)
contract.save()
len(contract.extra_datas) == 1
# #Res# #True
contract.extra_datas[0].extra_data_values == {'formula': 1}
# #Res# #True
contract.extra_datas[0].date == None
# #Res# #True

# #Comment# #New Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = change_extra_data
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = contract_start_date
new_endorsement.execute('start_endorsement')
new_endorsement.form.current_extra_data_date == None
# #Res# #True
new_endorsement.form.new_extra_data_date == None
# #Res# #True
new_endorsement.form.new_extra_data = {'formula': 3}
new_endorsement.execute('change_contract_extra_data_next')
new_endorsement.execute('apply_endorsement')
contract.save()

len(contract.extra_datas) == 1
# #Res# #True
contract.extra_datas[0].extra_data_values == {'formula': 3}
# #Res# #True
contract.extra_datas[0].date == None
# #Res# #True
