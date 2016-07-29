# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Loan Contract Creation
# #Comment# #Imports
import datetime
from proteus import config, Model, Wizard
from dateutil.relativedelta import relativedelta
from decimal import Decimal
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
# config.pool.test = True

# #Comment# #Install Modules
Module = Model.get('ir.module')
loan_module = Module.find([('name', '=', 'loan')])[0]
Module.install([loan_module.id], config.context)
wizard = Wizard('ir.module.install_upgrade')
wizard.execute('upgrade')

# #Comment# #Get Models
Account = Model.get('account.account')
AccountKind = Model.get('account.account.type')
Address = Model.get('party.address')
Company = Model.get('company.company')
Contract = Model.get('contract')
Country = Model.get('country.country')
FiscalYear = Model.get('account.fiscalyear')
Insurer = Model.get('insurer')
ItemDescription = Model.get('offered.item.description')
Loan = Model.get('loan')
LoanShare = Model.get('loan.share')
OptionDescription = Model.get('offered.option.description')
Party = Model.get('party.party')
Product = Model.get('offered.product')
Sequence = Model.get('ir.sequence')
SequenceType = Model.get('ir.sequence.type')
User = Model.get('res.user')
ZipCode = Model.get('country.zip')

# #Comment# #Constants
today = datetime.date.today()
product_start_date = datetime.date(2014, 1, 1)
contract_start_date = datetime.date(2014, 4, 10)

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

# #Comment# #Create Fiscal Year
fiscalyear = FiscalYear(name=str(today.year))
fiscalyear.start_date = today + relativedelta(month=1, day=1)
fiscalyear.end_date = today + relativedelta(month=12, day=31)
fiscalyear.company = company
post_move_seq = Sequence(name=str(today.year), code='account.move',
    company=company)
post_move_seq.save()
fiscalyear.post_move_sequence = post_move_seq
fiscalyear.save()
FiscalYear.create_period([fiscalyear.id], config.context)

# #Comment# #Create Account Kind
receivable_account_kind = AccountKind()
receivable_account_kind.name = 'Receivable Account Kind'
receivable_account_kind.company = company
receivable_account_kind.save()
payable_account_kind = AccountKind()
payable_account_kind.name = 'Payable Account Kind'
payable_account_kind.company = company
payable_account_kind.save()

# #Comment# #Create Account
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
coverage.currency = currency
coverage.name = 'Test Coverage'
coverage.code = 'test_coverage'
coverage.family = 'loan'
coverage.start_date = product_start_date
coverage.item_desc = item_description
coverage.insurer = insurer
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
product.currency = currency
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.start_date = product_start_date
product.coverages.append(coverage)
product.save()

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

receivable_account2 = Account()
receivable_account2.name = 'Account Receivable 2'
receivable_account2.code = 'account_receivable 2'
receivable_account2.kind = 'receivable'
receivable_account2.reconcile = True
receivable_account2.type = receivable_account_kind
receivable_account2.company = company
receivable_account2.save()
payable_account2 = Account()
payable_account2.name = 'Account Payable 2'
payable_account2.code = 'account_payable 2'
payable_account2.kind = 'payable'
payable_account2.type = payable_account_kind
payable_account2.company = company
payable_account2.save()

bank_party = Party(name='Bank Of Mordor')
bank_party.account_receivable = receivable_account2
bank_party.account_payable = payable_account2
lender = bank_party.lender_role.new()
bank_party.save()

zip_ = ZipCode(zip="1", city="Mount Doom", country=country)
zip_.save()
bank_address = Address(party=bank_party.id, zip="1", country=country,
    city="Mount Doom")
bank_address.save()

# #Comment# #Create Loans
loan_payment_date = datetime.date(2014, 5, 1)
loan_sequence = Sequence()
loan_sequence.name = 'Loan'
loan_sequence.code = 'loan'
loan_sequence.save()
loan_1 = Loan()
loan_1.lender_address = bank_address
loan_1.company = company
loan_1.kind = 'fixed_rate'
loan_1.funds_release_date = contract_start_date
loan_1.currency = currency
loan_1.first_payment_date = loan_payment_date
loan_1.rate = Decimal('0.045')
loan_1.amount = Decimal('250000')
loan_1.duration = 200
loan_1.save()
loan_2 = Loan()
loan_2.company = company
loan_2.lender_address = bank_address
loan_2.kind = 'fixed_rate'
loan_2.funds_release_date = contract_start_date
loan_2.currency = currency
loan_2.first_payment_date = loan_payment_date
loan_2.rate = Decimal('0.03')
loan_2.amount = Decimal('100000')
loan_2.duration = 220
loan_2.save()
Loan.calculate_loan([loan_1.id, loan_2.id], {})

loan_1.end_date == datetime.date(2030, 12, 1)
# #Res# #True
loan_2.end_date == datetime.date(2032, 8, 1)
# #Res# #True

# #Comment# #Create Test Contract
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
covered_element = contract.covered_elements.new()
covered_element.party = subscriber
option = covered_element.options[0]
option.coverage = coverage
loan_share_1 = option.loan_shares.new()
loan_share_1.loan = loan_1
loan_share_1.share = Decimal('0.7')
loan_share_2 = option.loan_shares.new()
loan_share_2.loan = loan_2
loan_share_2.share = Decimal('0.9')
contract.loans.append(loan_1)
contract.loans.append(loan_2)
contract.save()

Contract.button_calculate([contract.id], {})
contract = Contract(contract.id)
contract.covered_element_options[0].end_date == datetime.date(2032, 8, 1)
# #Res# #True

Loan.draft([loan_2.id], {})
loan_2.duration = 340
loan_2.save()
Loan.calculate_loan([loan_2.id], {})
loan_2 = Loan(loan_2.id)
loan_2.end_date == datetime.date(2042, 8, 1)
# #Res# #True

Contract.button_calculate([contract.id], {})
contract = Contract(contract.id)
contract.covered_element_options[0].end_date == datetime.date(2042, 8, 1)
# #Res# #True

Loan.draft([loan_2.id], {})
loan_2.duration = 100
loan_2.save()
Loan.calculate_loan([loan_2.id], {})
loan_2 = Loan(loan_2.id)
loan_2.end_date == datetime.date(2022, 8, 1)
# #Res# #True

Contract.button_calculate([contract.id], {})
contract = Contract(contract.id)
contract.covered_element_options[0].end_date == datetime.date(2030, 12, 1)
# #Res# #True
