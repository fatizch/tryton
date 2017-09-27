# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Deposit Management Scenario
# #Comment# #Imports
from decimal import Decimal
import datetime

from proteus import Model, Wizard

from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import create_fiscalyear
from trytond.modules.account_invoice.tests.tools import (
    set_fiscalyear_invoice_sequences)

# #Comment# #Install Modules
config = activate_modules('contract_cash_value')

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
Deposit = Model.get('contract.deposit')
Fee = Model.get('account.fee')
FiscalYear = Model.get('account.fiscalyear')
Invoice = Model.get('account.invoice')
ItemDescription = Model.get('offered.item.description')
Journal = Model.get('account.journal')
OptionDescription = Model.get('offered.option.description')
Party = Model.get('party.party')
PaymentTerm = Model.get('account.invoice.payment_term')
PaymentTermLine = Model.get('account.invoice.payment_term.line')
Product = Model.get('offered.product')
ProductTemplate = Model.get('product.template')
Rule = Model.get('rule_engine')
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
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(
    company, today=datetime.date(datetime.date.today().year, 1, 1)))
fiscalyear.click('create_period')

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
product_account.kind = 'other'
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

# #Comment# #Update cash journal
journal_cash, = Journal.find([('code', '=', 'CASH')])
journal_cash.debit_account = product_account
journal_cash.save()

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

# #Comment# #Create Fee
product_template = ProductTemplate()
product_template.name = 'Fee'
product_template.type = 'service'
# Assume Id('product', 'uom_unit') id is 1
product_template.default_uom = Uom(1)
product_template.list_price = Decimal(1)
product_template.cost_price = Decimal(0)
product_template.account_expense = product_account
product_template.account_revenue = product_account
product_template.save()
fee_product = AccountProduct()
fee_product.template = product_template
fee_product.type = 'service'
fee_product.default_uom = product_template.default_uom
fee_product.save()
fee = Fee()
fee.name = 'Test Fee'
fee.code = 'test_fee'
fee.type = 'percentage'
fee.rate = Decimal('0.15')
fee.frequency = 'once_per_invoice'
fee.product = fee_product
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

# #Comment# #Get premium rule
premium_rule, = Rule.find([('short_name', '=', 'simple_premium_rule')])

# #Comment# #Create Coverage
coverage = OptionDescription()
coverage.company = company
coverage.name = 'Test Coverage'
coverage.code = 'test_coverage'
coverage.family = 'cash_value'
coverage.is_cash_value = True
coverage.start_date = product_start_date
coverage.account_for_billing = product_account
coverage.item_desc = item_description
coverage.currency = currency
coverage.insurer = insurer
coverage_premium_rule = coverage.premium_rules.new()
coverage_premium_rule.rule = Rule(premium_rule.id)
coverage_premium_rule.rule_extra_data = {'premium_amount': 2000}
coverage_premium_rule.premium_base = 'contract.option'
coverage_premium_rule.frequency = 'monthly'
coverage_premium_rule.fees = [fee]
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
bank_party.save()
zip_ = ZipCode(zip="1", city="Mount Doom", country=country)
zip_.save()
bank_address = Address(party=bank_party.id, zip="1", country=country,
    city="Mount Doom")
bank_address.save()

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
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=freq_monthly, payment_term=payment_term))
contract.contract_number = '123456789'
contract.status = 'quote'
contract_fee = contract.fees.new()
contract_fee.fee = fee
contract.save()

Contract.calculate([contract.id], config._context)
_ = Contract.activate_contract([contract.id], config._context)

# #Comment# #Test deposit creation
invoice_wizard = Wizard('contract.do_invoice', [contract])
invoice_wizard.form.up_to_date = contract.start_date
invoice_wizard.execute('invoice')
invoice = contract.account_invoices[0]
invoice.click('post')
invoice.total_amount == Decimal('2300')  # 2000 premium + 15% fee
# #Res# #True

deposit, = Deposit.find([])
deposit.state == 'draft'
# #Res# #True
deposit.amount == Decimal('2000')
# #Res# #True
deposit.date is None
# #Res# #True
deposit.coverage == coverage
# #Res# #True

pay = Wizard('account.invoice.pay', [invoice])
pay.form.journal = journal_cash
pay.execute('choice')

deposit.reload()
deposit.state == 'received'
# #Res# #True
deposit.date == datetime.date.today()
# #Res# #True
