# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Loan Contract Creation
# #Comment# #Imports
import datetime
from proteus import Model, Wizard
from dateutil.relativedelta import relativedelta
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.contract_insurance_invoice.tests.tools import \
    add_invoice_configuration
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.offered_insurance.tests.tools import \
    add_insurer_to_product
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.premium.tests.tools import add_premium_rules


# Useful for updating the tests without having to recreate a db from scratch
# import os
# config = config.set_trytond(
#     database='postgresql://postgres:postgres@localhost:5432/test_db',
#     user='admin',
#     config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'workspace',
#         'conf', 'trytond.conf'))
# config.pool.test = True

# #Comment# #Install Modules
config = activate_modules(['account_payment_sepa_contract',
        'account_payment_clearing_cog'])

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
company_account.owners.append(Party(company.party.id))
company_account.currency = currency
company_account.number = 'ES8200000000000000000000'
company_account.save()

AccountAccount = Model.get('account.account')
bank_clearing = AccountAccount(parent=accounts['payable'].parent)
bank_clearing.name = 'Bank Clearing'
bank_clearing.type = accounts['payable'].type
bank_clearing.reconcile = True
bank_clearing.deferral = True
bank_clearing.kind = 'other'
bank_clearing.save()


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
journal = Journal()
journal.name = 'SEPA Journal'
journal.company = company
journal.currency = currency
journal.process_method = 'sepa'
journal.sepa_payable_flavor = 'pain.001.001.03'
journal.sepa_receivable_flavor = 'pain.008.001.02'
journal.sepa_charge_bearer = 'DEBT'
journal.sepa_bank_account_number = company_account.numbers[0]
journal.failure_billing_mode, = BillingMode.find([('code', '=',
    'monthly')])
journal.save()

Configuration = Model.get('account.configuration')
configuration = Configuration(1)
configuration.direct_debit_journal = journal
configuration.save()

AccountJournal = Model.get('account.journal')
expense, = AccountJournal.find([('code', '=', 'EXP')])
journal.clearing_account = bank_clearing
journal.clearing_journal = expense

journal.save()
FailureAction = Model.get('account.payment.journal.failure_action')
RejectReason = Model.get('account.payment.journal.reject_reason')
reject_reason = RejectReason()
reject_reason_2 = RejectReason()
reject_reason.code = 'reject_reason_code'
reject_reason.description = 'Reject Reason'
reject_reason.payment_kind = 'receivable'
reject_reason.process_method = 'sepa'
reject_reason.save()

reject_reason_2.code = 'reject_reason_2_code'
reject_reason_2.description = 'Reject Reason 2'
reject_reason_2.payment_kind = 'receivable'
reject_reason_2.process_method = 'sepa'
reject_reason_2.save()

insufficient_fund_reject_1 = FailureAction()
insufficient_fund_reject_1.reject_reason = reject_reason
insufficient_fund_reject_1.action = 'suspend'
insufficient_fund_reject_1.reject_number = 1
insufficient_fund_reject_1.journal = journal
insufficient_fund_reject_1.save()

# #Comment# #This failure action will not automatically un-suspend billing_info
insufficient_fund_reject_2 = FailureAction()
insufficient_fund_reject_2.reject_reason = reject_reason_2
insufficient_fund_reject_2.action = 'suspend_manual'
insufficient_fund_reject_2.reject_number = 1
insufficient_fund_reject_2.journal = journal
insufficient_fund_reject_2.save()
journal.reload()

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
monthly, = BillingMode.find([
        ('code', '=', 'monthly')])
contract_start_date = datetime.date.today()
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.contract_number = '123456789'
contract.save()
contract.billing_information.billing_mode = monthly
contract.billing_information. payment_term = monthly.allowed_payment_terms[0]
contract.billing_information.payer = subscriber
contract.billing_information.sepa_mandate = mandate
contract.billing_information.save()
contract, = Contract.find([])
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# Suspend payments
contract.billing_information.click('suspend_payments')
# #Comment# #Create invoice
ContractInvoice = Model.get('contract.invoice')
until_date = contract_start_date + relativedelta(months=1)
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')
contract_invoices = contract.invoices
invoice = contract_invoices[-1]

# #Comment# Post invoice
invoice.invoice.click('post')

# #Comment# Create payment
create_payment = Wizard('account.payment.creation')
create_payment.form.party = subscriber
create_payment.form.kind = 'receivable'
create_payment.form.free_motive = True
create_payment.form.payment_date = until_date
create_payment.form.journal = journal
MoveLine = Model.get('account.move.line')
for line in [x for x in invoice.invoice.move.lines if x.account.kind ==
        'receivable']:
    create_payment.form.lines_to_pay.append(MoveLine(line.id))
create_payment.form.description = "test"

# #Comment# #Create warning to simulate clicking yes
User = Model.get('res.user')
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = User(1)
warning.name = 'updating_payment_date_%s' % ('account.move.line,' +
    str(line.id))
warning.save()

create_payment.execute('create_payments')

# #Comment# No payments should be created
Payment = Model.get('account.payment')
len(Payment.find([()])) == 0
# #Res# #True

# #Comment# Unsuspend payments
contract.billing_information.click('unsuspend_payments')

create_payment = Wizard('account.payment.creation')
create_payment.form.party = subscriber
create_payment.form.kind = 'receivable'
create_payment.form.payment_date = until_date
create_payment.form.free_motive = True
create_payment.form.description = "test"
create_payment.form.journal = journal
MoveLine = Model.get('account.move.line')
for line in [x for x in invoice.invoice.move.lines if x.account.kind ==
        'receivable']:
    create_payment.form.lines_to_pay.append(MoveLine(line.id))

create_payment.form.description = "test"

# #Comment# #Create warning to simulate clicking yes
User = Model.get('res.user')
Warning = Model.get('res.user.warning')
warning = Warning()
warning.always = False
warning.user = User(1)
warning.name = 'updating_payment_date_%s' % ('account.move.line,' +
    str(line.id))
warning.save()

create_payment.execute('create_payments')

# #Comment# A payment should be created
Payment = Model.get('account.payment')
payment, = Payment.find([()])

# #Comment# Process payment
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('pre_process')
payment.reload()

# #Comment# Fail payment
fail_payment = Wizard('account.payment.manual_payment_fail', [payment])
fail_payment.form.reject_reason = reject_reason
payment.fail_code = reject_reason.code
fail_payment.execute('fail_payments')
payment.reload()

# #Comment# Billing information should now be suspended
contract.reload()
contract.billing_information.suspended is True
# #Res# #True

payment.click('succeed')
contract.billing_information.reload()

# #Comment# Billing information should now be automatically un-suspended
contract.billing_information.suspended is False
# #Res# #True

# #Comment# Fail payment again
fail_payment = Wizard('account.payment.manual_payment_fail', [payment])
fail_payment.form.reject_reason = reject_reason_2
payment.fail_code = reject_reason_2.code
fail_payment.execute('fail_payments')
payment.reload()

# #Comment# Billing information should be suspended
contract.reload()
contract.billing_information.suspended is True
# #Res# #True

payment.click('succeed')
contract.billing_information.reload()

# #Comment# Billing information should not be automatically un-suspended
contract.billing_information.suspended is True
# #Res# #True
