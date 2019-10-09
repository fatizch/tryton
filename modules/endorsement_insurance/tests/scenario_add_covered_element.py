# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Add covered element and advance contract
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules

from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.offered_insurance.tests.tools import init_insurance_product
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.party_cog.tests.tools import create_party_person

from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user

config = activate_modules(['endorsement_insurance'])
_ = create_country()

Module = Model.get('ir.module')

currency = get_currency(code='EUR')
_ = create_company(currency=currency)
company = get_company()

execute_test_case('authorizations_test_case')

product = init_insurance_product(user_context=False)
product = add_quote_number_generator(product)
product.save()

EndorsementPart = Model.get('endorsement.part')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')

modify_part, = EndorsementPart.find([('code', '=', 'modify_covered_elements')])
manage_options_part, = EndorsementPart.find([('code', '=', 'manage_options')])

manage = EndorsementDefinition()
manage.name = 'Remove Option'
manage.code = 'remove_option'
manage.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(endorsement_part=modify_part))
manage.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(endorsement_part=manage_options_part))
manage.save()

change_start_date_part, = EndorsementPart.find([('code', '=',
            'change_contract_start_date')])
change_start_date = EndorsementDefinition()
change_start_date.name = 'Change Start Date'
change_start_date.code = 'change_start_date'
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')
change_start_date.ordered_endorsement_parts.append(
    EndorsementDefinitionPartRelation(endorsement_part=change_start_date_part))
change_start_date.save()

config = switch_user('contract_user')

ItemDescription = Model.get('offered.item.description')
product = Model.get('offered.product')(product.id)
item_description = ItemDescription.find(
    [('kind', '=', 'person')])[0]


company = get_company()
product = Model.get('offered.product')(product.id)
item_description = ItemDescription.find(
    [('kind', '=', 'person')])[0]

subscriber = create_party_person(name="DUPONT", first_name="MARTIN")
subscriber.code = '2579'
subscriber.save()

new_party = create_party_person(name="DUPONT", first_name="ROGER")
new_party.code = '2580'
new_party.save()

new_party2 = create_party_person(name="DUPONT", first_name="PETER")
new_party2.code = '2581'
new_party2.save()

Contract = Model.get('contract')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = datetime.date(2019, 1, 1)
contract.product = product
covered_element = contract.covered_elements.new()
covered_element.party = subscriber
covered_element.item_desc = item_description
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

EndorsementDefinition = Model.get('endorsement.definition')
manage = EndorsementDefinition(manage.id)

# Add a covered element at contract start date
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = manage
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = contract.start_date
new_endorsement.execute('start_endorsement')
form = new_endorsement.form
form.click('add_covered_element', change=['all_covered',
        'current_covered', 'new_item_desc', 'contract', 'effective_date',
        'current_parent'])
new = form.current_covered[-1]
assert new.party is None, new.party.first_name
new.party = new_party
new.item_desc = item_description
new_endorsement.execute('modify_covered_element_next')
new_endorsement.execute('manage_options_next')
new_endorsement.execute('apply_endorsement')
contract.save()

assert len(contract.covered_elements) == 2
assert [len(cov.options) for cov in contract.covered_elements] == [1, 1]
roger_cov = contract.covered_elements[1]
assert roger_cov.party.first_name == 'ROGER'
assert roger_cov.options[0].start_date == contract.start_date

# Now , advance the contrat start date one month,
# we expect the new option to stick to contract start date
one_month_before = contract.start_date - relativedelta(months=1)
change_start_date = EndorsementDefinition(change_start_date.id)
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = change_start_date
new_endorsement.form.effective_date = one_month_before
new_endorsement.execute('start_endorsement')
new_endorsement.execute('change_start_date_next')
new_endorsement.execute('apply_endorsement')
contract.save()

assert contract.start_date == one_month_before
roger_cov.reload()
assert roger_cov.options[0].start_date == contract.start_date

# Second test:
# Add a covered element at date other than contract start date
one_month_after = contract.start_date + relativedelta(months=1)
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = manage
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = one_month_after
new_endorsement.execute('start_endorsement')
form = new_endorsement.form
form.click('add_covered_element', change=['all_covered',
        'current_covered', 'new_item_desc', 'contract', 'effective_date',
        'current_parent'])
new = form.current_covered[-1]
assert new.party is None, new.party.first_name
new.party = new_party2
new.item_desc = item_description
new_endorsement.execute('modify_covered_element_next')
new_endorsement.execute('manage_options_next')
new_endorsement.execute('apply_endorsement')
contract.save()

assert len(contract.covered_elements) == 3
assert [len(cov.options) for cov in contract.covered_elements] == [1, 1, 1]
peter_cov = contract.covered_elements[-1]
assert peter_cov.party.first_name == 'PETER'
assert peter_cov.options[0].start_date == one_month_after

# Now , advance the contrat start date one month,
# we expect the new option to keep its manual_start_date
one_month_before = contract.start_date - relativedelta(months=1)
change_start_date = EndorsementDefinition(change_start_date.id)
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = change_start_date
new_endorsement.form.effective_date = one_month_before
new_endorsement.execute('start_endorsement')
new_endorsement.execute('change_start_date_next')
new_endorsement.execute('apply_endorsement')
contract.save()

assert contract.start_date == one_month_before
peter_cov.reload()
assert peter_cov.options[0].start_date != contract.start_date
assert peter_cov.options[0].start_date == one_month_after
