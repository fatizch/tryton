# #Title# #TEST PARTY ENDORSEMENT
# #Comment# #Imports
import datetime
from proteus import config, Model, Wizard
from dateutil.relativedelta import relativedelta
from decimal import Decimal

from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.cog_utils.test_framework import test_values_against_model

# #Comment# #Init Database
config = config.set_trytond()
config.pool.test = True

# Useful for updating the tests without having to recreate a db from scratch
# import os
# config = config.set_trytond(
#    database='postgresql://tryton:tryton@localhost:5432/test_db_22',
#    user='admin',
#    config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
#        'conf', 'trytond.conf'))


# #Comment# #Install Modules
Module = Model.get('ir.module')
endorsement_module = Module.find([('name', '=', 'endorsement_party')])[0]
Module.install([endorsement_module.id], config.context)
wizard = Wizard('ir.module.install_upgrade')
wizard.execute('upgrade')

# #Comment# #Get Models
Address = Model.get('party.address')
Company = Model.get('company.company')
Contract = Model.get('contract')
Country = Model.get('country.country')
Currency = Model.get('currency.currency')
CurrencyRate = Model.get('currency.currency.rate')
Endorsement = Model.get('endorsement')
EndorsementContract = Model.get('endorsement.contract')
EndorsementContractField = Model.get('endorsement.contract.field')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')
EndorsementPart = Model.get('endorsement.part')
Party = Model.get('party.party')
User = Model.get('res.user')
ZipCode = Model.get('country.zipcode')

# #Comment# #Constants
today = datetime.date.today()
endorsement_effective_date = datetime.date(2014, 10, 21)

# #Comment# #Create or fetch Currency
currencies = Currency.find([('code', '=', 'USD')])
if not currencies:
    currency = Currency(name='US Dollar', symbol=u'$', code='USD',
        rounding=Decimal('0.01'), mon_grouping='[]',
        mon_decimal_point='.')
    currency.save()
    CurrencyRate(date=today + relativedelta(month=1, day=1),
        rate=Decimal('1.0'), currency=currency).save()
else:
    currency, = currencies

# #Comment# #Create or fetch Country
countries = Country.find([('code', '=', 'FR')])
if not countries:
    country = Country(name='France', code='FR')
    country.save()
else:
    country, = countries

# #Comment# #Create Company
_ = create_company(currency=currency)
company = get_company()

# #Comment# #Reload the context
config._context = User.get_preferences(True, config.context)
config._context['company'] = company.id

# #Comment# #Create Change Address Endorsement
change_address_part = EndorsementPart()
change_address_part.name = 'Change Address'
change_address_part.code = 'change_address'
change_address_part.kind = 'party'
change_address_part.view = 'change_party_address'
change_address_part.save()
change_address_def = EndorsementDefinition()
change_address_def.name = 'Change Address'
change_address_def.code = 'change_address'
change_address_def.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(endorsement_part=change_address_part))
change_address_def.save()

# #Comment# #Create or fetch Country
countries = Country.find([('code', '=', 'FR')])
if not countries:
    country = Country(name='France', code='FR')
    country.save()
else:
    country, = countries

paris1 = ZipCode(zip='75001', city='PARIS', country=country.id)
paris2 = ZipCode(zip='75002', city='PARIS', country=country.id)
paris1.save()
paris2.save()

original_data = {
    'name': 'name1',
    'start_date': datetime.date(2000, 1, 1),
    'street': 'street1',
    'streetbis': 'streetbis1',
    'zip_and_city': paris1}

new_data = {
    'name': 'name2',
    'street': 'street2',
    'streetbis': 'streetbis2',
    'zip_and_city': paris2}

# #Comment# #Create john
john = create_party_person(company=company)
address1 = john.addresses[0]
for k, v in original_data.iteritems():
    setattr(address1, k, v)
john.save()
john, = Party.find(['name', '=', 'Doe'])
len(john.addresses)
# #Res# #1

# #Comment# #New Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.party = john
new_endorsement.form.endorsement_definition = change_address_def
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = endorsement_effective_date
new_endorsement.execute('start_endorsement')

base_address = new_endorsement.form.displayers[0].new_address[0]
test_values_against_model(base_address, original_data)
base_address.end_date = endorsement_effective_date + relativedelta(days=-1)

new_displayer = new_endorsement.form.displayers.new()
for k, v in new_data.iteritems():
    setattr(new_displayer.new_address[0], k, v)
new_endorsement.execute('change_party_address_next')
new_endorsement.execute('apply_endorsement')
john.save()

john, = Party.find(['name', '=', 'Doe'])
len(john.addresses)
# #Res# #2
base_address = Address(john.addresses[0].id)
test_values_against_model(base_address, original_data)
base_address.end_date == datetime.date(2014, 10, 20)
# #Res# #True

new_address = Address(john.addresses[1].id)
test_values_against_model(new_address, new_data)
new_address.end_date == None
# #Res# #True
new_address.start_date == endorsement_effective_date
# #Res# #True

good_endorsement, = Endorsement.find([])
Endorsement.cancel([good_endorsement.id], config._context)
john.save()

john, = Party.find(['name', '=', 'Doe'])
len(john.addresses)
# #Res# #1
test_values_against_model(john.addresses[0], original_data)
