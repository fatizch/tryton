# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Start Date Endorsement Scenario
# #Comment# #Imports
from decimal import Decimal
import datetime
from dateutil.relativedelta import relativedelta

from proteus import Model

from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company

# #Comment# #Install Modules
config = activate_modules('contract_loan_invoice')

# #Comment# #Get Models
Account = Model.get('account.account')
AccountInvoice = Model.get('account.invoice')
AccountProduct = Model.get('product.product')
AccountKind = Model.get('account.account.type')
Address = Model.get('party.address')
BillingInformation = Model.get('contract.billing_information')
BillingMode = Model.get('offered.billing_mode')
Company = Model.get('company.company')
Contract = Model.get('contract')
ContractInvoice = Model.get('contract.invoice')
ContractPremium = Model.get('contract.premium')
Country = Model.get('country.country')
Fee = Model.get('account.fee')
FiscalYear = Model.get('account.fiscalyear')
InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
ItemDescription = Model.get('offered.item.description')
Loan = Model.get('loan')
LoanShare = Model.get('loan.share')
OptionDescription = Model.get('offered.option.description')
Party = Model.get('party.party')
PaymentTerm = Model.get('account.invoice.payment_term')
PaymentTermLine = Model.get('account.invoice.payment_term.line')
Product = Model.get('offered.product')
ProductTemplate = Model.get('product.template')
Sequence = Model.get('ir.sequence')
SequenceStrict = Model.get('ir.sequence.strict')
SequenceType = Model.get('ir.sequence.type')
Uom = Model.get('product.uom')
User = Model.get('res.user')
Insurer = Model.get('insurer')
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
_ = create_company(currency=currency)
company = get_company()

# #Comment# #Reload the context
config._context = User.get_preferences(True, config.context)
config._context['company'] = company.id

# #Comment# #Create Fiscal Year
fiscalyear = FiscalYear(name='2014')
fiscalyear.start_date = datetime.date(datetime.date.today().year, 1, 1)
fiscalyear.end_date = datetime.date(datetime.date.today().year, 12, 31)
fiscalyear.company = company
post_move_seq = Sequence(name='2014', code='account.move',
    company=company)
post_move_seq.save()
fiscalyear.post_move_sequence = post_move_seq
seq = SequenceStrict(name='2014',
    code='account.invoice', company=company)
seq.save()
bool(fiscalyear.invoice_sequences.pop())
# #Res# #True

fiscalyear.save()
invoice_sequence = InvoiceSequence()
invoice_sequence.out_invoice_sequence = seq
invoice_sequence.in_invoice_sequence = seq
invoice_sequence.out_credit_note_sequence = seq
invoice_sequence.in_credit_note_sequence = seq
invoice_sequence.fiscalyear = fiscalyear
invoice_sequence.company = company
invoice_sequence.save()

fiscalyear.reload()
FiscalYear.create_period([fiscalyear.id], config.context)

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

# #Comment# #Create billing modes
payment_term = PaymentTerm()
payment_term.name = 'direct'
payment_term.lines.append(PaymentTermLine())
payment_term.save()
freq_monthly = BillingMode()
freq_monthly.name = 'Monthly'
freq_monthly.code = 'monthly'
freq_monthly.frequency = 'monthly'
freq_monthly.allowed_payment_terms.append(payment_term)
freq_monthly.save()
freq_yearly = BillingMode()
freq_yearly.name = 'Yearly'
freq_yearly.code = 'yearly'
freq_yearly.frequency = 'yearly'
freq_yearly.allowed_payment_terms.append(PaymentTerm.find([])[0])
freq_yearly.save()

# #Comment# #Create Fee
product_template = ProductTemplate()
product_template.name = 'Fee'
product_template.type = 'service'
# Assume Id('product', 'uom_unit') id is 1
product_template.default_uom = Uom(1)
product_template.list_price = Decimal(1)
product_template.cost_price = Decimal(0)
product_template.save()
product = AccountProduct()
product.template = product_template
product.type = 'service'
product.default_uom = product_template.default_uom
product.save()
fee = Fee()
fee.name = 'Test Fee'
fee.code = 'test_fee'
fee.type = 'fixed'
fee.amount = Decimal('20')
fee.frequency = 'once_per_contract'
fee.product = product
fee.save()

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
coverage.family = 'loan'
coverage.start_date = product_start_date
coverage.account_for_billing = product_account
coverage.item_desc = item_description
coverage.currency = currency
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
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.currency = currency
product.quote_number_sequence = quote_sequence
product.start_date = product_start_date
product.billing_modes.append(freq_monthly)
product.billing_modes.append(freq_yearly)
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

bank_party = Party()
bank_party.name = 'Bank of Mordor'
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
loan_1.lender = bank_party
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
loan_2.lender = bank_party
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
ordered_loan = contract.ordered_loans.new()
ordered_loan.loan = loan_1
ordered_loan.number = 1
ordered_loan = contract.ordered_loans.new()
ordered_loan.loan = loan_2
ordered_loan.number = 2
loan_share_1 = option.loan_shares.new()
loan_share_1.loan = loan_1
loan_share_1.share = Decimal('0.7')
loan_share_2 = option.loan_shares.new()
loan_share_2.loan = loan_2
loan_share_2.share = Decimal('0.9')
contract_premium = contract.premiums.new()
contract_premium.start = contract_start_date
contract_premium.amount = Decimal('2')
contract_premium.frequency = 'monthly'
contract_premium.account = product_account
contract_premium.rated_entity = fee
option_premium_1 = option.premiums.new()
option_premium_1.start = contract_start_date
option_premium_1.amount = Decimal('20')
option_premium_1.frequency = 'monthly'
option_premium_1.account = product_account
option_premium_1.rated_entity = coverage
option_premium_1.loan = loan_1
option_premium_2 = option.premiums.new()
option_premium_2.start = contract_start_date
option_premium_2.amount = Decimal('200')
option_premium_2.frequency = 'monthly'
option_premium_2.account = product_account
option_premium_2.rated_entity = coverage
option_premium_2.loan = loan_2
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=freq_yearly, payment_term=payment_term))
contract.contract_number = '123456789'
contract.status = 'active'
contract.save()

# #Comment# #Test loan_share end_date calculation
new_share_date = datetime.date(2014, 9, 12)
option = contract.covered_elements[0].options[0]
loan_share_3 = LoanShare()
loan_share_3.start_date = new_share_date
loan_share_3.loan = loan_1
loan_share_3.share = Decimal('0.5')
loan_share_3.option = option
loan_share_3.save()
loan_share_1 = LoanShare(
    contract.covered_elements[0].options[0].loan_shares[0].id)
loan_share_1.end_date == datetime.date(2014, 9, 11)
# #Res# #True
loan_share_3.end_date == loan_1.end_date
# #Res# #True
LoanShare.delete([loan_share_3])