# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Third Party Right Management Scenario
# #Title# #Renewal of a contract
# #Comment# #Imports

import datetime as dt
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.party_cog.tests.tools import create_party_person, \
    create_party_company
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user

# #Comment# #Install Modules

config = activate_modules([
     'third_party_right_management', 'contract_insurance_suspension',
     'contract_term_renewal'],
    cache_file_name='third_party_right_management_scen_2')

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
coverage.start_date = dt.date(2014, 1, 1)
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

Rule = Model.get('rule_engine')
renewal_rule = product.term_renewal_rule.new()
renewal_rule.allow_renewal = True
subscription_date_sync_rule, = Rule.find([
        ('short_name', '=', 'product_term_renewal_sync_sub_date')])
renewal_rule.rule = subscription_date_sync_rule
renewal_rule.product = product
renewal_rule.save()
product.save()

# #Comment# #Create Subscriber

config = switch_user('contract_user')
subscriber = create_party_person()

# #Comment# #Create a manager

config = switch_user('admin')
party_manager = create_party_company()

# #Comment# #Create Protocol

ThirdPartyManager = Model.get('third_party_manager')
Protocol = Model.get('third_party_manager.protocol')
EventType = Model.get('event.type')

manager = ThirdPartyManager()
manager.party = party_manager
manager.save()

protocol = Protocol()
protocol.name = "Basic Protocol"
protocol.code = "BASIC"
protocol.third_party_manager = manager
watched_events = protocol.watched_events.find([
        ('code', 'in', [
                'activate_contract', 'hold_contract', 'renew_contract']),
        ])
protocol.watched_events.extend(watched_events)
protocol.save()

# #Comment# #Create Contract

config = switch_user('contract_user')
Contract = Model.get('contract')

protocol = Model.get('third_party_manager.protocol')(protocol.id)
coverage = Model.get('offered.option.description')(coverage.id)
item_description = Model.get('offered.item.description')(item_description.id)

contract = Contract()
company = Model.get('company.company')(company.id)
# #Comment# #To avoid leap years issues with tests, it's better to chose a fixed
# #Comment# contract start date
contract_start_date = dt.date(2015, 1, 1)
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.status = 'quote'
product = Model.get('offered.product')(product.id)
contract.product = product
contract.contract_number = '123456789'
covered_element = contract.covered_elements.new()
covered_element.party = subscriber
covered_element.item_desc = item_description
option = covered_element.options.new()
option.coverage = coverage
contract.save()

ProtocolCoverage = Model.get(
    'third_party_manager.protocol-offered.option.description')
pc = ProtocolCoverage(coverage=option.coverage, protocol=protocol)
pc.save()

Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #Renew the contract

config._context['client_defined_date'] = contract_start_date + \
    dt.timedelta(days=60)
renew_wizard = Wizard('contract_term_renewal.renew', models=[contract])
renew_wizard.execute('renew')

contract.reload()
option, = contract.covered_elements[0].options
tpp = option.third_party_periods[-1]
(tpp.end_date - contract_start_date).days
# #Res# #730