# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Third Party Right Management Scenario
# #Title# #Endorsement support
# #Comment# #Imports

import datetime as dt
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.company.tests.tools import get_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.party_cog.tests.tools import (
    create_party_company, create_party_person)
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user

# #Comment# #Constants

product_start_date = dt.date(2014, 1, 1)
contract_start_date = dt.date(2014, 4, 10)
new_contract_start_date = dt.date(2014, 10, 21)

# #Comment# #Install Modules

config = activate_modules(['third_party_right_management',
        'contract_insurance_suspension', 'endorsement'],
    cache_file_name='third_party_right_management_scen_1')

# #Comment# #Create country

_ = create_country()

# #Comment# #Create currency

currency = get_currency(code='EUR')

# #Comment# #Create Company

_ = create_company(currency=currency)

# #Comment# #Switch user

execute_test_case('authorizations_test_case')
config = switch_user('financial_user')
company = get_company()

# #Comment# #Create Fiscal Year

fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
fiscalyear.click('create_period')

# #Comment# #Create chart of accounts

_ = create_chart(company)
accounts = get_accounts(company)

# #Comment# #Create Account Kind
AccountKind = Model.get('account.account.type')
product_account_kind = AccountKind()
product_account_kind.name = 'Product Account Kind'
product_account_kind.company = company
product_account_kind.statement = 'income'
product_account_kind.revenue = True
product_account_kind.save()
receivable_account_kind = AccountKind()
receivable_account_kind.name = 'Receivable Account Kind'
receivable_account_kind.company = company
receivable_account_kind.statement = 'balance'
receivable_account_kind.receivable = True
receivable_account_kind.save()
payable_account_kind = AccountKind()
payable_account_kind.name = 'Payable Account Kind'
payable_account_kind.company = company
payable_account_kind.statement = 'balance'
payable_account_kind.payable = True
payable_account_kind.save()

# #Comment# #Create Account
Account = Model.get('account.account')
product_account = Account()
product_account.name = 'Product Account'
product_account.code = 'product_account'
product_account.type = product_account_kind
product_account.company = company
product_account.save()

receivable_account = Account()
receivable_account.name = 'Account Receivable'
receivable_account.code = 'account_receivable'
receivable_account.type = receivable_account_kind
receivable_account.reconcile = True
receivable_account.company = company
receivable_account.party_required = True
receivable_account.save()

payable_account = Account()
payable_account.name = 'Account Payable'
payable_account.code = 'account_payable'
payable_account.type = payable_account_kind
payable_account.company = company
payable_account.party_required = True
payable_account.save()

# #Comment# #Create Insurer
config = switch_user('product_user')
company = get_company()
currency = get_currency(code='EUR')

Insurer = Model.get('insurer')
Party = Model.get('party.party')
Account = Model.get('account.account')
insurer = Insurer()
insurer.party = Party()
insurer.party.name = 'Insurer'
insurer.party.account_receivable = Account(receivable_account.id)
insurer.party.account_payable = Account(payable_account.id)
insurer.party.save()
insurer.save()

# #Comment# #Create Item Description
ItemDescription = Model.get('offered.item.description')
item_description = ItemDescription()
item_description.name = 'Test Item Description'
item_description.code = 'test_item_description'
item_description.kind = 'person'
item_description.save()

# #Comment# #Create Product
SequenceType = Model.get('ir.sequence.type')
Sequence = Model.get('ir.sequence')
OptionDescription = Model.get('offered.option.description')
Product = Model.get('offered.product')
SubStatus = Model.get('contract.sub_status')

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
coverage.start_date = contract_start_date
coverage.item_desc = item_description
coverage.insurer = insurer
coverage.subscription_behaviour = 'optional'
coverage.account_for_billing = Model.get('account.account')(product_account.id)
coverage.save()
product = Product()
product.company = company
product.currency = currency
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.start_date = dt.date(2014, 1, 1)
product.coverages.append(coverage)
product.save()

# #Comment# #Create Protocol

ThirdPartyManager = Model.get('third_party_manager')
Protocol = Model.get('third_party_manager.protocol')
EventType = Model.get('event.type')
manager = ThirdPartyManager()
manager.party = create_party_company()
manager.save()
protocol = Protocol()
protocol.name = "Basic Protocol"
protocol.code = "BASIC"
protocol.third_party_manager = manager
watched_events = protocol.watched_events.find([
        ('code', 'in', ['activate_contract', 'apply_endorsement']),
        ])
protocol.watched_events.extend(watched_events)
protocol.save()

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
change_start_date_part.third_party_protocols.append(protocol)
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

# #Comment# #Create Test Contract

config = switch_user('contract_user')
subscriber = create_party_person()

coverage = Model.get('offered.option.description')(coverage.id)
item_description = Model.get('offered.item.description')(item_description.id)

Contract = Model.get('contract')
contract = Contract()
company = Model.get('company.company')(company.id)
contract.start_date = contract_start_date
contract.product = Model.get('offered.product')(product.id)
contract.contract_number = '1111'
covered_element = contract.covered_elements.new()
covered_element.party = subscriber
covered_element.item_desc = item_description
option = covered_element.options.new()
option.coverage = coverage
contract.save()

ProtocolCoverage = Model.get(
    'third_party_manager.protocol-offered.option.description')
pc = ProtocolCoverage(
    coverage=option.coverage,
    protocol=Model.get('third_party_manager.protocol')(protocol.id))
pc.save()
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #There is now one period

contract.reload()
option, = contract.covered_elements[0].options
tpp, = option.third_party_periods
tpp.start_date - contract_start_date == dt.timedelta(0)
# #Res# #True
tpp.end_date is None
# #Res# #True

# #Comment# #New Endorsement

Endorsement = Model.get('endorsement')
EndorsementDefinition = Model.get('endorsement.definition')
change_start_date = EndorsementDefinition(change_start_date.id)
new_endorsement = Wizard('endorsement.start')
new_endorsement.form.contract = contract
new_endorsement.form.endorsement_definition = change_start_date
new_endorsement.form.endorsement = None
new_endorsement.form.applicant = None
new_endorsement.form.effective_date = new_contract_start_date
new_endorsement.execute('start_endorsement')
new_endorsement.execute('change_start_date_next')
new_endorsement.execute('suspend')
good_endorsement, = Endorsement.find([
        ('contracts', '=', contract.id)])
_ = Endorsement.apply_synchronous([good_endorsement.id], config._context)

# #Comment# #There is now two periods

contract.reload()
option, = contract.covered_elements[0].options
len(option.third_party_periods)
# #Res# #1
tpp = option.third_party_periods[0]
tpp.start_date - new_contract_start_date == dt.timedelta(0)
# #Res# #True
tpp.end_date is None
# #Res# #True
