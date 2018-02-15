# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Start Date Endorsement Scenario
# #Comment# #Imports
import datetime
from proteus import Model, Wizard
from dateutil.relativedelta import relativedelta
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.company.tests.tools import get_company

from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user

# #Comment# #Install Modules
config = activate_modules('endorsement')

# #Comment# #Constants
today = datetime.date.today()
product_start_date = datetime.date(2014, 1, 1)
contract_start_date = datetime.date(2014, 4, 10)
new_contract_start_date = datetime.date(2014, 10, 21)

# #Comment# #Create or fetch Currency
currency = get_currency(code='EUR')

# #Comment# #Create or fetch Country
Country = Model.get('country.country')
countries = Country.find([('code', '=', 'FR')])
if not countries:
    country = Country(name='France', code='FR')
    country.save()
else:
    country, = countries

# #Comment# #Create Company
currency = get_currency(code='EUR')
_ = create_company(currency=currency)

execute_test_case('authorizations_test_case')
config = switch_user('product_user')
company = get_company()
currency = get_currency(code='EUR')

# #Comment# #Create Product
SequenceType = Model.get('ir.sequence.type')
Sequence = Model.get('ir.sequence')
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

OptionDescription = Model.get('offered.option.description')
coverage = OptionDescription()
coverage.company = company
coverage.currency = currency
coverage.name = 'Test Coverage'
coverage.code = 'test_coverage'
coverage.start_date = product_start_date
coverage.save()

Product = Model.get('offered.product')
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
EndorsementPart = Model.get('endorsement.part')
change_start_date_part = EndorsementPart()
change_start_date_part.name = 'Change Start Date'
change_start_date_part.code = 'change_start_date'
change_start_date_part.kind = 'contract'
change_start_date_part.view = 'change_start_date'
EndorsementContractField = Model.get('endorsement.contract.field')
Field = Model.get('ir.model.field')
change_start_date_part.contract_fields.append(
    EndorsementContractField(field=Field.find([
                ('model.model', '=', 'contract'),
                ('name', '=', 'start_date')])[0].id))
change_start_date_part.save()
EndorsementDefinition = Model.get('endorsement.definition')
change_start_date = EndorsementDefinition()
change_start_date.name = 'Change Start Date'
change_start_date.code = 'change_start_date'
EndorsementDefinitionPartRelation = Model.get(
    'endorsement.definition-endorsement.part')
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

config = switch_user('contract_user')
company = get_company()
currency = get_currency(code='EUR')

Contract = Model.get('contract')
Product = Model.get('offered.product')
product = Product(product.id)

# #Comment# #Create Test Contract
contract = Contract()
contract.company = company
contract.start_date = contract_start_date
contract.product = product
contract.contract_number = '1111'
contract.status = 'active'
contract.save()

# #Comment# #New Endorsement
EndorsementDefinition = Model.get('endorsement.definition')
change_start_date = EndorsementDefinition(change_start_date.id)
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
Endorsement = Model.get('endorsement')
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

config = switch_user('admin')

Option = Model.get('contract.option')
Contract = Model.get('contract')
contract = Contract(contract.id)
Option.delete([contract.options[0]])
contract = Contract(contract.id)
len(contract.options) == 0
# #Res# #True

config = switch_user('contract_user')
Endorsement = Model.get('endorsement')
Endorsement.cancel([good_endorsement.id], config._context)
Contract = Model.get('contract')
contract = Contract(contract.id)
len(contract.options) == 1
# #Res# #True

# #Comment# #Test Terminate Endorsement

EndorsementDefinition = Model.get('endorsement.definition')
terminate_contract = EndorsementDefinition(terminate_contract.id)
SubStatus = Model.get('contract.sub_status')
terminated_status, = SubStatus.find([('code', '=', 'terminated')])


def get_terminated(contract, effective_date):
    new_endorsement = Wizard('endorsement.start')
    new_endorsement.form.contract = contract
    new_endorsement.form.endorsement_definition = terminate_contract
    new_endorsement.form.endorsement = None
    new_endorsement.form.applicant = None
    new_endorsement.form.effective_date = effective_date
    new_endorsement.execute('start_endorsement')
    new_endorsement.form.termination_reason = terminated_status
    new_endorsement.execute('terminate_contract_next')
    new_endorsement.execute('apply_endorsement')
    return Contract(contract.id)


def get_cancelled():
    good_endorsement, = Endorsement.find([
            ('contracts', '=', contract.id),
            ('state', '=', 'applied')])
    Endorsement.cancel([good_endorsement.id], config._context)
    return Contract(contract.id)

start_plus_three = contract_start_date + relativedelta(months=3)
contract = get_terminated(contract, start_plus_three)
contract.start_date == contract_start_date
# #Res# #True
contract.initial_start_date == contract_start_date
# #Res# #True
contract.status == 'terminated'
# #Res# #True
contract.end_date == start_plus_three
# #Res# #True
contract.termination_reason == terminated_status
# #Res# #True

contract = get_cancelled()
contract.start_date == contract_start_date
# #Res# #True
contract.end_date is None
# #Res# #True
contract.termination_reason is None
# #Res# #True


# #Comment# #Test Terminate Endorsement with several terms
# contract_start_date = datetime.date(2014, 4, 10)
first_term_end = datetime.date(2015, 4, 9)
contract.end_date = first_term_end
contract.save()


History = Model.get('contract.activation_history')
for start, end in [
        ((2015, 4, 10), (2016, 4, 9)),
        ((2016, 4, 10), (2017, 4, 9))]:
    history = History(start_date=datetime.date(*start),
        end_date=datetime.date(*end), contract=contract.id)
    history.save()

# #Comment# #Case 0 : today is in second term, we end in second term

first_month_second_term = datetime.date(2015, 4, 20)
config._context['client_defined_date'] = first_month_second_term
contract.reload()
second_term_end = contract.activation_history[1].end_date
assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
contract = get_terminated(contract, first_month_second_term)
assert len(contract.activation_history) == 2, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == first_month_second_term
assert contract.termination_reason == terminated_status

contract = get_cancelled()
assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == second_term_end
assert contract.termination_reason is None

# #Comment# #Case 1 : today is in first term, we end before first_term_end

config._context['client_defined_date'] = first_term_end
contract.reload()
assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
contract = get_terminated(contract, start_plus_three)
assert len(contract.activation_history) == 1, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == start_plus_three
assert contract.termination_reason == terminated_status

contract = get_cancelled()
assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == first_term_end
assert contract.termination_reason is None

# #Comment# #Case 1b : today is in first term, we end at first_term_end

assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
contract = get_terminated(contract, first_term_end)
assert len(contract.activation_history) == 1, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == first_term_end
assert contract.termination_reason == terminated_status

contract = get_cancelled()
assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == first_term_end
assert contract.termination_reason is None

# #Comment# #Case 2: today is in second term, we terminate before first_term_end
config._context['client_defined_date'] = datetime.date(2015, 4, 10)
contract.reload()
assert contract.end_date == second_term_end
User = Model.get('res.user')
user, = User.find(['login', '=', 'contract_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'termination_before_active_start_date_%s' % str(contract.id)
warning.save()

contract = get_terminated(contract, start_plus_three)
assert len(contract.activation_history) == 1, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == start_plus_three
assert contract.termination_reason == terminated_status

contract = get_cancelled()
assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == second_term_end
assert contract.termination_reason is None

# #Comment# #Case 2b: today is in second term, we terminate at first_term_end
config._context['client_defined_date'] = datetime.date(2015, 4, 10)
contract.reload()
second_term_end = contract.activation_history[1].end_date
assert contract.end_date == second_term_end
User = Model.get('res.user')
user, = User.find(['login', '=', 'contract_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'termination_before_active_start_date_%s' % str(contract.id)
warning.save()

contract = get_terminated(contract, first_term_end)
assert len(contract.activation_history) == 1, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == first_term_end
assert contract.termination_reason == terminated_status

contract = get_cancelled()
assert len(contract.activation_history) == 3, [(x.start_date, x.end_date,
    x.termination_reason) for x in contract.activation_history]
assert contract.end_date == second_term_end
assert contract.termination_reason is None

# #Comment# #Test Void Endorsement
config._context['client_defined_date'] = first_term_end

contract.reload()
User = Model.get('res.user')
user, = User.find(['login', '=', 'contract_user'])
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = user
warning.name = 'void_renewed_contract'
warning.save()

void_contract = EndorsementDefinition(void_contract.id)
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
contract.start_date is None
# #Res# #True
contract.initial_start_date == contract_start_date
# #Res# #True
contract.status == 'void'
# #Res# #True
contract.sub_status == error
# #Res# #True
