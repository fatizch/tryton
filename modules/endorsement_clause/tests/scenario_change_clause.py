# #Title# #Loan Endorsement Scenario
# #Comment# #Imports
import datetime
from proteus import config, Model, Wizard

# #Comment# #Init Database
config = config.set_trytond()
config.pool.test = True
# Useful for updating the tests without having to recreate a db from scratch
#  import os
#  config = config.set_trytond(
#     database='postgresql://tryton:tryton@localhost:5432/test_db',
#     user='admin',
#     language='en_US',
#     config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
#         'conf', 'trytond.conf'))
#  config.pool.test = True

# #Comment# #Install Modules
Module = Model.get('ir.module')
endorsement_clause_module = Module.find([
        ('name', '=', 'endorsement_clause')])[0]
Module.install([endorsement_clause_module.id], config.context)
wizard = Wizard('ir.module.install_upgrade')
wizard.execute('upgrade')

# #Comment# #Get Models
Clause = Model.get('clause')
Company = Model.get('company.company')
Contract = Model.get('contract')
Country = Model.get('country.country')
Currency = Model.get('currency.currency')
Endorsement = Model.get('endorsement')
EndorsementDefinition = Model.get('endorsement.definition')
EndorsementPart = Model.get('endorsement.part')
EndorsementPartOrdered = Model.get('endorsement.definition-endorsement.part')
Group = Model.get('res.group')
Party = Model.get('party.party')
Product = Model.get('offered.product')
Sequence = Model.get('ir.sequence')
User = Model.get('res.user')

# #Comment# #Fetch Currency
euro = Currency.find([('code', '=', 'EUR')])[0]

# #Comment# #Create or fetch Country
countries = Country.find([('code', '=', 'FR')])
if not countries:
    country = Country(name='France', code='FR')
    country.save()
else:
    country, = countries

# #Comment# #Create Company
comp_party = Party(name='Main Company')
comp_party.save()
company = Company(party=comp_party, currency=euro)
company.save()
user = User(1)
user.main_company = company
user.company = company
user.save()

# #Comment# #Reload the context
config._context = User.get_preferences(True, config.context)
config._context['company'] = company.id

# #Comment# #Create test clauses
clause_1 = Clause(name='Clause 1', code='clause_1', customizable=False,
    content='Clause 1')
clause_1.save()
clause_2 = Clause(name='Clause 2', code='clause_2', customizable=True,
    content='Clause 2')
clause_2.save()
clause_3 = Clause(name='Clause 3', code='clause_3', customizable=False,
    content='Clause 3')
clause_3.save()


# #Comment# #Create Product
contract_sequence = Sequence()
contract_sequence.name = 'Contract Sequence'
contract_sequence.code = 'contract'
contract_sequence.company = company
contract_sequence.save()
quote_sequence = Sequence()
quote_sequence.name = 'Quote Sequence'
quote_sequence.code = 'quote'
quote_sequence.company = company
quote_sequence.save()
product = Product()
product.company = company
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.clauses.append(clause_1)
product.clauses.append(clause_2)
product.save()

# #Comment# #Create Endorsement Definition
change_clause = EndorsementPart.find([('code', '=', 'change_clauses')])[0]
manage_clauses = EndorsementDefinition(name='Manage Clauses',
    code='manage_clauses')
manage_clauses.ordered_endorsement_parts.append(
    EndorsementPartOrdered(endorsement_part=change_clause, order=1))
manage_clauses.save()

# #Comment# #Create Subscriber
subscriber = Party(is_person=True, name='Subscriber', first_name='John',
    birth_date=datetime.date(1990, 2, 15), gender='male')
subscriber.save()

# #Comment# #Create Contract
start_date = datetime.date(2020, 5, 12)
contract = Contract(product=product, subscriber=subscriber, status='active',
    company=company, start_date=start_date, contract_number='123')
contract.save()

# #Comment# #Test Endorsement
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = manage_clauses
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = start_date
new_endorsement.execute('start_endorsement')
{x.id for x in new_endorsement.form.possible_clauses} == {
    clause_1.id, clause_2.id}
# #Res# #True
new_endorsement.form.contract.contract == contract
# #Res# #True
new_endorsement.form.new_clause = clause_1
new_endorsement.form.click('add_clause', change=['contract', 'current_clauses',
        'new_clause', 'possible_clauses'])
new_endorsement.form.new_clause == None
# #Res# #True
{x.id for x in new_endorsement.form.possible_clauses} == {clause_2.id}
# #Res# #True
len(new_endorsement.form.current_clauses) == 1
# #Res# #True
new_endorsement.form.current_clauses[0].action == 'added'
# #Res# #True
new_endorsement.form.current_clauses[0].clause == clause_1
# #Res# #True
new_endorsement.form.current_clauses[0].clause_id == None
# #Res# #True
new_endorsement.form.current_clauses[0].customizable is False
# #Res# #True
new_endorsement.form.current_clauses[0].text == 'Clause 1'
# #Res# #True
new_endorsement.form.click('add_text_clause', change=['contract',
        'current_clauses'])
len(new_endorsement.form.current_clauses) == 2
# #Res# #True
new_endorsement.form.current_clauses[1].action == 'added'
# #Res# #True
new_endorsement.form.current_clauses[1].clause == None
# #Res# #True
new_endorsement.form.current_clauses[1].clause_id == None
# #Res# #True
new_endorsement.form.current_clauses[1].customizable is True
# #Res# #True
new_endorsement.form.current_clauses[1].text == ''
# #Res# #True
new_endorsement.form.current_clauses[1].text = 'Custo 1'
new_endorsement.form.click('add_text_clause', change=['contract',
        'current_clauses'])
new_endorsement.form.current_clauses[2].text = 'Custo 2'
new_endorsement.form.current_clauses[2].action = 'removed'
new_endorsement.execute('manage_clauses_next')
new_endorsement.execute('summary_previous')
[(x.action, x.text) for x in new_endorsement.form.current_clauses] == [
    ('added', 'Clause 1'), ('added', 'Custo 1')]
# #Res# #True
new_endorsement.execute('manage_clauses_next')
new_endorsement.execute('apply_endorsement')

[(x.clause, x.text) for x in contract.clauses] == [(clause_1, 'Clause 1'),
    (None, 'Custo 1')]
# #Res# #True

# #Comment# #Try again
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = manage_clauses
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = start_date
new_endorsement.execute('start_endorsement')
{x.id for x in new_endorsement.form.possible_clauses} == {clause_2.id}
# #Res# #True
len(new_endorsement.form.current_clauses) == 2
# #Res# #True
new_endorsement.form.current_clauses[0].action == 'nothing'
# #Res# #True
new_endorsement.form.current_clauses[0].clause == clause_1
# #Res# #True
new_endorsement.form.current_clauses[0].clause_id == contract.clauses[0].id
# #Res# #True
new_endorsement.form.current_clauses[0].customizable is False
# #Res# #True
new_endorsement.form.current_clauses[0].text == 'Clause 1'
# #Res# #True
new_endorsement.form.current_clauses[1].action == 'nothing'
# #Res# #True
new_endorsement.form.current_clauses[1].clause == None
# #Res# #True
new_endorsement.form.current_clauses[1].clause_id == contract.clauses[1].id
# #Res# #True
new_endorsement.form.current_clauses[1].customizable is True
# #Res# #True
new_endorsement.form.current_clauses[1].text == 'Custo 1'
# #Res# #True
new_endorsement.form.current_clauses[0].action = 'removed'
new_endorsement.form.current_clauses[1].text = 'Modified Custo 1'
new_endorsement.form.current_clauses[1].action == 'modified'
# #Res# #True
new_endorsement.form.current_clauses[1].action = 'nothing'
new_endorsement.form.current_clauses[1].text == 'Custo 1'
# #Res# #True

new_endorsement.form.new_clause = clause_2
new_endorsement.form.click('add_clause', change=['contract', 'current_clauses',
        'new_clause', 'possible_clauses'])
[(x.action, x.text) for x in new_endorsement.form.current_clauses] == [
    ('removed', 'Clause 1'), ('nothing', 'Custo 1'), ('added', 'Clause 2')]
# #Res# #True
new_endorsement.form.current_clauses[2].customizable is True
# #Res# #True
new_endorsement.execute('manage_clauses_next')
new_endorsement.execute('summary_previous')
[(x.action, x.text) for x in new_endorsement.form.current_clauses] == [
    ('nothing', 'Custo 1'), ('added', 'Clause 2'), ('removed', 'Clause 1')]
# #Res# #True
new_endorsement.execute('manage_clauses_next')
new_endorsement.execute('apply_endorsement')

contract = Contract(contract.id)
[(x.clause, x.text) for x in contract.clauses] == [
    (None, 'Custo 1'), (clause_2, 'Clause 2')]
# #Res# #True

# #Comment# #Test Endorsement Cancellation
endorsement_last, endorsement_first = Endorsement.find([],
    order=[('create_date', 'DESC')])
endorsement_last.click('cancel')

contract = Contract(contract.id)
[(x.clause, x.text) for x in contract.clauses] == [(clause_1, 'Clause 1'),
    (None, 'Custo 1')]
# #Res# #True

endorsement_first.click('cancel')
contract = Contract(contract.id)
contract.clauses == []
# #Res# #True
