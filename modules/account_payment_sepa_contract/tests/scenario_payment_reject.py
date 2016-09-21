# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Payment SEPA Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from proteus import config, Model, Wizard
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts
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

config = config.set_trytond()
config.pool.test = True

# #Comment# #Install Modules
Module = Model.get('ir.module')
payment_sepa_module = Module.find(
    [('name', '=', 'account_payment_sepa_contract')])[0]
payment_sepa_module.click('install')
Wizard('ir.module.install_upgrade').execute('upgrade')

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

Number = Model.get('bank.account.number')
banks = Bank.find([])
Account = Model.get('bank.account')
company_account = Account()
company_account.bank = bank
company_account.owners.append(company.party)
company_account.currency = currency
company_account.number = 'ES8200000000000000000000'
company_account.save()

# #Comment# #Create Product
product = init_product()
product = add_quote_number_generator(product)
product = add_premium_rules(product)
product = add_invoice_configuration(product, accounts)
product = add_insurer_to_product(product)
product.save()

# #Comment# #Create Payment Journal
BillingMode = Model.get('offered.billing_mode')

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
journal_SEPA.save()
Configuration = Model.get('account.configuration')
configuration = Configuration(1)
configuration.direct_debit_journal = journal_SEPA
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
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=monthly_direct_debit,
        payment_term=monthly_direct_debit.allowed_payment_terms[0],
        direct_debit_day=5,
        payer=subscriber,
        direct_debit_account=subscriber_account))
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
        ('account.kind', '=', 'receivable')])
payment.date = payment.line.payment_date
initial_payment_date = payment.date
payment.save()
payment.click('approve')
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('process')

# #Comment# #Fail payment
payment.sepa_return_reason_code = 'BE04'
payment.save()
config._context['client_defined_date'] = initial_payment_date + \
    relativedelta(days=10)
payment.click('fail')
payment.line.payment_date
payment.manual_fail_status == 'pending'
# #Res# #True

# #Comment# #Create second invoice
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
        ('account.kind', '=', 'receivable'),
        ('origin', '=', 'account.invoice,%s' % second_invoice.invoice.id)])
payment.date = payment.line.payment_date
initial_payment_date = payment.date
payment.save()
payment.click('approve')
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('process')

# #Comment# #Fail payment
payment.sepa_return_reason_code = 'AM04'
payment.save()
config._context['client_defined_date'] = initial_payment_date + \
    relativedelta(days=10)
payment.click('fail')
payment.line.payment_date == initial_payment_date + relativedelta(months=1)
# #Res# #True
payment.manual_fail_status

# #Comment# #Create third invoice
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
        ('account.kind', '=', 'receivable'),
        ('origin', '=', 'account.invoice,%s' % second_invoice.invoice.id)])
payment_second_invoice.date = payment_second_invoice.line.payment_date
initial_payment_date = payment_second_invoice.date
payment_second_invoice.save()
payment_second_invoice.click('approve')

payment_third_invoice = Payment()
payment_third_invoice.company = company
payment_third_invoice.journal = journal_SEPA
payment_third_invoice.kind = 'receivable'
payment_third_invoice.amount = third_invoice.invoice.total_amount
payment_third_invoice.party = subscriber
payment_third_invoice.line, = MoveLine.find([('party', '=', subscriber.id),
        ('account.kind', '=', 'receivable'),
        ('origin', '=', 'account.invoice,%s' % third_invoice.invoice.id)])
payment_third_invoice.date = payment_third_invoice.line.payment_date
initial_payment_date = payment.date
payment_third_invoice.save()
payment_third_invoice.click('approve')
payments = [payment_second_invoice, payment_third_invoice]
process_payment = Wizard('account.payment.process', payments)
process_payment.execute('process')

# #Comment# #Fail payments
payment_second_invoice.sepa_return_reason_code = 'AM04'
payment_second_invoice.merged_id = '123456'
payment_second_invoice.save()
payment_third_invoice.sepa_return_reason_code = 'AM04'
payment_third_invoice.merged_id = '123456'
payment_third_invoice.save()
config._context['client_defined_date'] = initial_payment_date + \
    relativedelta(days=10)
Payment.fail([p.id for p in payments], config._context)
payment_second_invoice.line.payment_date
payment_third_invoice.line.payment_date
payment_second_invoice.manual_fail_status
payment_third_invoice.manual_fail_status
len(contract.billing_informations)
# #Res# #2
contract.billing_informations[-1].date == third_invoice.end + \
    relativedelta(days=1)
# #Res# #True
contract.reload()
len(contract.invoices) == 4
# #Res# #True
