# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Payment Reject Before Contract Start Date
# #Comment# #Imports
import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts, create_tax
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.contract_insurance_invoice.tests.tools import \
    add_invoice_configuration
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.offered_insurance.tests.tools import \
    add_insurer_to_product
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.premium.tests.tools import add_premium_rules

# #Comment# #Install Modules
config = activate_modules(['account_payment_sepa_contract',
        'account_payment_clearing_contract'],
    cache_file_name='scenario_payment_with_clearing')

# #Comment# #Create country
_ = create_country()

# #Comment# #Create currenct
currency = get_currency(code='EUR')

# #Comment# #Create Company
_ = create_company(currency=currency)
company = get_company()

# #Comment# #Reload the context
User = Model.get('res.user')
config._context = User.get_preferences(True, config.context)

# #Comment# #Create Fiscal Year
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
fiscalyear.click('create_period')
second_fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company,
    datetime.date.today() + relativedelta(years=1)))
second_fiscalyear.click('create_period')

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)
Bank = Model.get('bank')
Party = Model.get('party.party')
party_bank = Party()
party_bank.name = 'Bank'
party_bank.save()
bank = Bank()
bank.party = party_bank
bank.bic = 'NSMBFRPPXXX'
bank.save()
expense = accounts['expense']
revenue = accounts['revenue']

Number = Model.get('bank.account.number')
banks = Bank.find([])
Account = Model.get('bank.account')
company_account = Account()
company_account.bank = bank
company_account.owners.append(company.party)
company_account.currency = currency
company_account.number = 'ES8200000000000000000000'
company_account.save()

# #Comment# #Create tax

tax = create_tax(Decimal('.10'))
tax.save()

# #Comment# #Create Account Product

ProductUom = Model.get('product.uom')
unit, = ProductUom.find([('name', '=', 'Unit')])
ProductTemplate = Model.get('product.template')
Product = Model.get('product.product')
account_product = Product()

ProductCategory = Model.get('product.category')
account_category = ProductCategory(name="Account Category")
account_category.accounting = True
account_category.account_expense = expense
account_category.account_revenue = revenue
account_category.customer_taxes.append(tax)
account_category.code = 'account_category'
account_category.save()

template = ProductTemplate()
template.name = 'product'
template.default_uom = unit
template.type = 'service'
template.list_price = Decimal('40')
template.cost_price = Decimal('25')
template.account_category = account_category
template.products[0].code = 'product'
template.save()
account_product = template.products[0]

Sequence = Model.get('ir.sequence')
Journal = Model.get('account.journal')
sequence_journal, = Sequence.find([('code', '=', 'account.journal')])
reject_fee_journal = Journal(
    name='Write-Off',
    type='write-off',
    sequence=sequence_journal)
reject_fee_journal.save()

# #Comment# #Create Product
product = init_product()
product = add_quote_number_generator(product)
product = add_premium_rules(product)
product = add_invoice_configuration(product, accounts)
product = add_insurer_to_product(product)
product.save()

Fee = Model.get('account.fee')
Coverage = Model.get('offered.option.description')

# #Comment# #Create Payment Journal
BillingMode = Model.get('offered.billing_mode')

AccountJournal = Model.get('account.journal')
Journal = Model.get('account.payment.journal')
journal_SEPA = Journal()
journal_SEPA.name = 'SEPA Journal'
journal_SEPA.company = company
journal_SEPA.currency = currency
journal_SEPA.process_method = 'sepa'
journal_SEPA.sepa_payable_flavor = 'pain.001.001.03'
journal_SEPA.sepa_receivable_flavor = 'pain.008.001.02'
journal_SEPA.sepa_charge_bearer = 'DEBT'
journal_SEPA.sepa_bank_account_number = company_account.numbers[0]
journal_SEPA.failure_billing_mode, = BillingMode.find([('code', '=',
    'quarterly')])
journal_SEPA.clearing_account = accounts['cash']
journal_SEPA.clearing_journal, = AccountJournal.find([('code', '=', 'CASH')])
journal_SEPA.save()
Configuration = Model.get('account.configuration')
configuration = Configuration(1)
configuration.direct_debit_journal = journal_SEPA
configuration.reject_fee_journal = reject_fee_journal
configuration.save()
FailureAction = Model.get('account.payment.journal.failure_action')
RejectReason = Model.get('account.payment.journal.reject_reason')
insufficient_fund_reject_1 = FailureAction()
insufficient_fund_reject_1.reject_reason, = RejectReason.find([
        ('code', '=', 'AM04')])
insufficient_fund_reject_1.action = 'retry'
insufficient_fund_reject_1.reject_number = 1
insufficient_fund_reject_1.journal = journal_SEPA
insufficient_fund_reject_1.save()
insufficient_fund_reject_2 = FailureAction()
insufficient_fund_reject_2.reject_reason = \
    insufficient_fund_reject_1.reject_reason
insufficient_fund_reject_2.action = 'move_to_manual_payment'
insufficient_fund_reject_2.reject_number = 2
insufficient_fund_reject_2.journal = journal_SEPA
insufficient_fund_reject_2.save()
invalid_adress_reject = FailureAction()
invalid_adress_reject.reject_reason, = RejectReason.find([
        ('code', '=', 'BE04')])
invalid_adress_reject.action = 'manual'
invalid_adress_reject.journal = journal_SEPA
invalid_adress_reject.save()
outdated = FailureAction()
outdated.reject_reason, = RejectReason.find([
        ('code', '=', 'TM01')])
outdated.action = 'present_again_after'
outdated.journal = journal_SEPA
outdated.present_again_day = '24'
outdated.save()
reject_fee = Fee(name='fee', code='fee', company=company,
    frequency='once_per_invoice', type='fixed', amount=Decimal('6.00'))
reject_fee.coverages.append(Coverage(product.coverages[0].id))
reject_fee.product = Product(account_product.id)
reject_fee.save()
outdated.rejected_payment_fee = reject_fee
outdated.save()

# #Comment# #Create Subscriber
subscriber = create_party_person()

# #Comment# #Create SEPA mandate
subscriber_account = Account()
subscriber_account.bank = bank
subscriber_account.owners.append(subscriber)
subscriber_account.currency = currency
subscriber_account.number = 'BE82068896274468'
subscriber_account.save()

Mandate = Model.get('account.payment.sepa.mandate')
mandate = Mandate()
mandate.company = company
mandate.party = subscriber
mandate.account_number = subscriber_account.numbers[0]
mandate.identification = 'MANDATE'
mandate.type = 'recurrent'
mandate.signature_date = datetime.date.today()
mandate.save()
mandate.click('request')
mandate.click('validate_mandate')

# #Comment# #Create Contract
BillingMode = Model.get('offered.billing_mode')
monthly_direct_debit, = BillingMode.find([
        ('code', '=', 'monthly_direct_debit')])
contract_start_date = datetime.date.today()
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.billing_informations[0].billing_mode = monthly_direct_debit
contract.billing_informations[0].direct_debit_day = 5
contract.billing_informations[0].payer = subscriber
contract.billing_informations[0].direct_debit_account = subscriber_account
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #Create first invoice
ContractInvoice = Model.get('contract.invoice')
Contract.first_invoice([contract.id], config.context)
first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
first_invoice.invoice.click('post')

# #Comment# #Create and process first Payment
MoveLine = Model.get('account.move.line')
Payment = Model.get('account.payment')
payment = Payment()
payment.company = company
payment.journal = journal_SEPA
payment.kind = 'receivable'
payment.amount = first_invoice.invoice.total_amount
payment.party = subscriber
payment.line, = MoveLine.find([('party', '=', subscriber.id),
        ('account.type.receivable', '=', True)])
payment.date = payment.line.payment_date
first_payment_date = payment.date
cur_payment_date = payment.date
payment.save()
payment.click('approve')
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('pre_process')

# #Comment# #Fail payment
config._context['client_defined_date'] = cur_payment_date + \
    relativedelta(days=10)
be04, = RejectReason.find([
        ('code', '=', 'BE04')])
RejectPayment = Wizard('account.payment.manual_payment_fail',
    [payment])
RejectPayment.form.reject_reason = be04
RejectPayment.execute('fail_payments')
payment.reload()
payment.line.payment_date
payment.manual_fail_status == 'pending'
# #Res# #True

# #Comment# #Create second invoice
if contract_start_date.month != (contract_start_date +
        relativedelta(days=1)).month:
    # End of month, we must go to the end of next month to trigger a new
    # invoice
    until_date = contract_start_date + relativedelta(days=1)
    until_date = until_date + relativedelta(months=1)
    until_date = until_date + relativedelta(days=-1)
else:
    until_date = contract_start_date + relativedelta(months=1)
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')
len(contract.invoices)
# #Res# #2
second_invoice = contract.invoices[0]
second_invoice.invoice.click('post')

# #Comment# #Create and process second Payment
MoveLine = Model.get('account.move.line')
Payment = Model.get('account.payment')
payment = Payment()
payment.company = company
payment.journal = journal_SEPA
payment.kind = 'receivable'
payment.amount = second_invoice.invoice.total_amount
payment.party = subscriber
payment.line, = MoveLine.find([('party', '=', subscriber.id),
        ('account.type.receivable', '=', True),
        ('move.origin', '=', 'account.invoice,%s' % second_invoice.invoice.id)])
payment.date = payment.line.payment_date
cur_payment_date = payment.date
payment.save()
payment.click('approve')
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('pre_process')

# #Comment# #Fail payment
config._context['client_defined_date'] = cur_payment_date + \
    relativedelta(days=10)
am04, = RejectReason.find([
        ('code', '=', 'AM04')])
RejectPayment = Wizard('account.payment.manual_payment_fail',
    [payment])
RejectPayment.form.reject_reason = am04
RejectPayment.execute('fail_payments')
payment.reload()
assert payment.line.payment_date == cur_payment_date + relativedelta(
    months=1), (payment.line.payment_date, cur_payment_date)
payment.manual_fail_status

# #Comment# #Create third invoice
if contract_start_date.month != (contract_start_date +
        relativedelta(days=1)).month:
    # End of month, we must go to the end of next month to trigger a new
    # invoice
    until_date = contract_start_date + relativedelta(days=1)
    until_date = until_date + relativedelta(months=2)
    until_date = until_date + relativedelta(days=-1)
else:
    until_date = contract_start_date + relativedelta(months=2)
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')
contract.reload()
len(contract.invoices)
# #Res# #3
third_invoice = contract.invoices[0]
third_invoice.invoice.click('post')

# #Comment# #Create payment for second and third invoice
payment_second_invoice = Payment()
payment_second_invoice.company = company
payment_second_invoice.journal = journal_SEPA
payment_second_invoice.kind = 'receivable'
payment_second_invoice.amount = second_invoice.invoice.total_amount
payment_second_invoice.party = subscriber
payment_second_invoice.line, = MoveLine.find([('party', '=', subscriber.id),
        ('account.type.receivable', '=', True),
        ('move.origin', '=', 'account.invoice,%s' % second_invoice.invoice.id)])
payment_second_invoice.date = payment_second_invoice.line.payment_date
cur_payment_date = payment_second_invoice.date
payment_second_invoice.save()
payment_second_invoice.click('approve')

payment_third_invoice = Payment()
payment_third_invoice.company = company
payment_third_invoice.journal = journal_SEPA
payment_third_invoice.kind = 'receivable'
payment_third_invoice.amount = third_invoice.invoice.total_amount
payment_third_invoice.party = subscriber
payment_third_invoice.line, = MoveLine.find([('party', '=', subscriber.id),
        ('account.type.receivable', '=', True),
        ('move.origin', '=', 'account.invoice,%s' % third_invoice.invoice.id)])
payment_third_invoice.date = payment_third_invoice.line.payment_date
cur_payment_date = payment.date
payment_third_invoice.save()
payment_third_invoice.click('approve')
payments = [payment_second_invoice, payment_third_invoice]
process_payment = Wizard('account.payment.process', payments)
process_payment.execute('pre_process')

len(contract.billing_informations) == 1
# #Res# #True

contract.billing_informations[0].date is None
# #Res# #True

# #Comment# #Fail payments
config._context['client_defined_date'] = contract.initial_start_date - \
    relativedelta(days=10)
RejectPayment = Wizard('account.payment.manual_payment_fail',
    payments)
RejectPayment.form.reject_reason = am04
RejectPayment.execute('fail_payments')
payment_second_invoice.reload()
payment_third_invoice.reload()

payment_second_invoice.line.payment_date
payment_third_invoice.line.payment_date
payment_second_invoice.manual_fail_status
payment_third_invoice.manual_fail_status

contract.reload()
len(contract.billing_informations)
# #Res# #1
contract.billing_informations[0].date is None
# #Res# #True
contract.billing_informations[-1].billing_mode == \
    journal_SEPA.failure_billing_mode
# #Res# #True
