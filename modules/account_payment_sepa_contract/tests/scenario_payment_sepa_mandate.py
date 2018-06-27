# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Loan Contract Creation
# #Comment# #Imports
import datetime
from decimal import Decimal
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
    add_invoice_configuration, create_billing_mode
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
config = activate_modules(['account_payment_sepa_contract', 'batch_launcher'])

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

today = datetime.date.today()
contract_start_date = datetime.date(day=1, month=today.month, year=today.year
    ) - relativedelta(months=1)
config._context['client_defined_date'] = contract_start_date

# #Comment# #Create Fiscal Year
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company,
    today=contract_start_date))
fiscalyear.click('create_period')
second_fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company,
    contract_start_date + relativedelta(years=1)))
second_fiscalyear.click('create_period')

IrModel = Model.get('ir.model')
MoveLine = Model.get('account.move.line')
BatchParameter = Model.get('batch.launcher.parameter')

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

party_bank2 = Party()
party_bank2.name = 'Bank 2'
party_bank2.save()
bank2 = Bank()
bank2.party = party_bank2
bank2.bic = 'BDFEFRPP'
bank2.save()

party_bank3 = Party()
party_bank3.name = 'Bank 3'
party_bank3.save()
bank3 = Bank()
bank3.party = party_bank3
bank3.bic = 'RBOSGIGI'
bank3.save()

party_bank3 = Party()
party_bank3.name = 'Bank 3'
party_bank3.save()
bank4 = Bank()
bank4.party = party_bank3
bank4.bic = 'MUCBPKKA'
bank4.save()

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
journal.allow_group_deletion = True
journal.save()

Configuration = Model.get('account.configuration')
configuration = Configuration(1)
configuration.direct_debit_journal = journal
configuration.save()

AccountJournal = Model.get('account.journal')
expense, = AccountJournal.find([('code', '=', 'EXP')])
journal.clearing_account = bank_clearing
journal.clearing_journal = expense
# #Comment# #Create Subscriber
subscriber = create_party_person()
subscriber2 = create_party_person(name='other')

# #Comment# #Create SEPA mandate (mandate = subcriber, mandate 2,3,4 =
# #Comment# #subscriber2)
subscriber_account = Account()
subscriber_account.bank = bank
subscriber_account.owners.append(subscriber)
subscriber_account.currency = currency
subscriber_account.number = 'BE82068896274468'
subscriber_account.save()

subscriber2_account = Account()
subscriber2_account.bank = bank2
subscriber2_account.owners.append(subscriber2)
subscriber2_account.currency = currency
subscriber2_account.number = 'FR7630001007941234567890185'
subscriber2_account.save()

subscriber2_account_2 = Account()
subscriber2_account_2.bank = bank3
subscriber2_account_2.owners.append(Party(subscriber2.id))
subscriber2_account_2.currency = currency
subscriber2_account_2.number = 'GI75NWBK000000007099453'
subscriber2_account_2.save()

subscriber2_account_3 = Account()
subscriber2_account_3.bank = bank4
subscriber2_account_3.owners.append(Party(subscriber2.id))
subscriber2_account_3.currency = currency
subscriber2_account_3.number = 'PK36SCBL0000001123456702'
subscriber2_account_3.save()


Mandate = Model.get('account.payment.sepa.mandate')
mandate = Mandate()
mandate.company = company
mandate.party = subscriber
mandate.account_number = subscriber_account.numbers[0]
mandate.identification = 'MANDATE'
mandate.type = 'recurrent'
mandate.signature_date = contract_start_date
mandate.save()
mandate.click('request')
mandate.click('validate_mandate')

mandate2 = Mandate()
mandate2.company = company
mandate2.party = subscriber2
mandate2.account_number = subscriber2_account.numbers[0]
mandate2.identification = 'MANDATE 2'
mandate2.type = 'recurrent'
mandate2.signature_date = contract_start_date
mandate2.save()
mandate2.click('request')
mandate2.click('validate_mandate')

mandate3 = Mandate()
mandate3.company = company
mandate3.party = subscriber2
mandate3.account_number = subscriber2_account_2.numbers[0]
mandate3.identification = 'mandate 3'
mandate3.type = 'recurrent'
mandate3.signature_date = contract_start_date
mandate3.save()
mandate3.click('request')
mandate3.click('validate_mandate')

mandate4 = Mandate()
mandate4.company = company
mandate4.party = subscriber2
mandate4.account_number = subscriber2_account_3.numbers[0]
mandate4.identification = 'mandate 4'
mandate4.type = 'recurrent'
mandate4.signature_date = contract_start_date
mandate4.save()
mandate4.click('request')
mandate4.click('validate_mandate')

# #Comment# #Create Contract
monthly, = BillingMode.find([
        ('code', '=', 'monthly_direct_debit'), ('direct_debit', '=', True)])
monthly_manual, = BillingMode.find([
        ('code', '=', 'monthly'), ('direct_debit', '=', False)])
PaymentTerm = Model.get('account.invoice.payment_term')
payment_term_percent = PaymentTerm(name='Term percent')
line = payment_term_percent.lines.new(type='percent', ratio=Decimal('.5'))
delta = line.relativedeltas.new(days=0)
line = payment_term_percent.lines.new(type='remainder')
delta = line.relativedeltas.new(days=15)
payment_term_percent.save()
monthly_percent = create_billing_mode('monthly',
    payment_term_percent.id, direct_debit=True, code='monthly_percent')
product.billing_modes.append(monthly_percent)
product.save()

Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')


contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
# #Comment# #Remove default billing mode
bool(contract.billing_informations.pop(0))
# #Res# #True

# #Comment# #Add billing information with monthly billing monde and mandate
# #Comment# # as sepa mandate
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=monthly,
        payment_term=monthly.allowed_payment_terms[0],
        payer=subscriber,
        direct_debit_day=5,
        sepa_mandate=mandate))
contract.contract_number = '123456789'
contract.billing_informations[0].direct_debit_account = \
    mandate.account_number.account
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

contract2 = Contract()
contract2.company = company
contract2.subscriber = subscriber2
contract2.start_date = contract_start_date
contract2.product = product
# #Comment# #Remove default billing mode
bool(contract2.billing_informations.pop(0))
# #Res# #True
# #Comment# #Add billing information with monthly billing monde and mandate2
# #Comment# # as sepa mandate
monthly_percent = BillingMode(monthly_percent.id)
contract2.billing_informations.append(BillingInformation(date=None,
        billing_mode=monthly_percent,
        payment_term=monthly_percent.allowed_payment_terms[0],
        payer=subscriber2,
        direct_debit_day=5,
        sepa_mandate=mandate2))
contract2.contract_number = '123456780'
contract2.billing_informations[0].direct_debit_account = \
    mandate2.account_number.account
contract2.save()
Wizard('contract.activate', models=[contract2]).execute('apply')

# #Comment# #Create invoices
until_date = contract_start_date + relativedelta(months=1)
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')
contract.reload()
contract_invoices = contract.invoices

len(contract_invoices) == 2
# #Res# #True

contract_invoice_2, contract_invoice = contract_invoices

generate_contract_2_invoice = Wizard('contract.do_invoice', models=[contract2])
generate_contract_2_invoice.form.up_to_date = until_date
generate_contract_2_invoice.execute('invoice')
contract_invoices2 = contract2.invoices

contract_2_invoice_2, contract_2_invoice = contract_invoices2

# #Comment# #Post contract invoices
contract_invoice.invoice.click('post')
contract_invoice_2.invoice.click('post')
contract_invoice_2.invoice.save()

# Post contract2 invoices
contract_2_invoice.invoice.click('post')
contract_2_invoice_2.invoice.click('post')
contract_2_invoice_2.invoice.save()

# #Comment# #Because the current billing information on the contract has
# a SEPA mandate
# #Comment# #For now we have a sepa mandate on the contract_invoice_2.
contract_invoice_2.invoice.sepa_mandate == mandate
# #Res# #True

# #Comment# #Because the current billing information on the contract has a
# SEPA mandate
# #Comment# #For now we have a sepa mandate on the contract_2_invoice_2.
# #Comment# #We'll add a billing information without sepa mandate later.
contract_2_invoice_2.invoice.sepa_mandate == mandate2
# #Res# #True

# #Comment# #Add a billing information at the contract_invoice_2 payment date
# #Comment# #without SEPA mandate.
# #Comment# #So the related invoice will not have a sepa mandate defined.
billing_information_no_sepa = BillingInformation(
    date=contract_invoice_2.invoice.lines_to_pay[0].payment_date,
    billing_mode=monthly_manual,
    payment_term=monthly_manual.allowed_payment_terms[0],
    payer=subscriber,
    sepa_mandate=None)
contract.billing_informations.append(billing_information_no_sepa)
contract.save()
contract_invoice_2.reload()

# #Comment# #Add a billing information at the contract_2_invoice_2 payment date
# #Comment# #without SEPA mandate.
# #Comment# #So the related invoice will not have a sepa mandate defined.
billing_information_no_sepa_2 = BillingInformation(
        date=contract_2_invoice_2.invoice.lines_to_pay[0].payment_date,
        billing_mode=monthly_manual,
        payment_term=monthly_manual.allowed_payment_terms[0],
        payer=subscriber2,
        contract=contract2,
        direct_debit=False,
        sepa_mandate=None)
billing_information_no_sepa_2.save()
contract2.reload()
contract_2_invoice_2.reload()

contract_invoice.invoice.sepa_mandate == mandate
# #Res# #True
contract_2_invoice.invoice.sepa_mandate == mandate2
# #Res# #True
contract_invoice_2.invoice.sepa_mandate is None
# #Res# #True
contract_2_invoice_2.invoice.sepa_mandate is None
# #Res# #True

# #Comment# #Set a sepa mandate on the billing_information_no_sepa to generate
# #Comment# #a SEPA payment
billing_information_no_sepa.billing_mode = monthly
billing_information_no_sepa.payment_term = monthly.allowed_payment_terms[0]
billing_information_no_sepa.direct_debit_day = 5
billing_information_no_sepa.sepa_mandate = mandate
billing_information_no_sepa.direct_debit_account = \
    mandate.account_number.account
billing_information_no_sepa.save()
contract.reload()
contract_invoice_2.reload()

# #Comment# #Generate SEPA payment for the  contract_invoice_2 (1 line, 1
# #Comment# #payment)
create_payment = Wizard('account.payment.creation')
create_payment.form.party = contract.subscriber
create_payment.form.kind = 'receivable'
create_payment.form.payment_date = \
    contract_invoice_2.invoice.lines_to_pay[0].payment_date
create_payment.form.free_motive = True
create_payment.form.journal = journal

MoveLine = Model.get('account.move.line')
for line in [x for x in contract_invoice_2.invoice.move.lines
        if x.account.kind == 'receivable']:
    line._parent = None
    line._parent_field_name = None
    line._parent_name = None
    create_payment.form.lines_to_pay.append(MoveLine(line.id))

create_payment.form.description = "test"
create_payment.form.bank_account = mandate.account_number.account

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

# #Comment# #A single payment should be created
Payment = Model.get('account.payment')
payment, = Payment.find([()])

# #Comment# #We remove sepa mandate on the billing information
# #Comment# #used to generate the previous payment just before processing it
billing_information_no_sepa.billing_mode = monthly_manual
billing_information_no_sepa.payment_term = \
    monthly_manual.allowed_payment_terms[0]
billing_information_no_sepa.direct_debit_day = None
billing_information_no_sepa.sepa_mandate = None
billing_information_no_sepa.direct_debit_account = None
billing_information_no_sepa.save()

# #Comment# Process payment
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('pre_process')

# #Comment# #Billing information sepa mandate has been set to None again
# #Comment# #But there is a payment with the previous sepa mandate.
# #Comment# #So the sepa_mandate on both the invoice and the line_to_pay will
# #Comment# #not be None but the same mandate of the payment
payment.sepa_mandate.id == contract_invoice_2.invoice.sepa_mandate.id == \
    contract_invoice_2.invoice.lines_to_pay[0].sepa_mandate.id == mandate.id
# #Res# #True

# #Comment# #Check that removing the payment date on the line removes the
# #Comment# #sepa mandate on the line and the invoice:
save_payment_date = contract_invoice_2.invoice.lines_to_pay[0].payment_date
contract_invoice_2.invoice.lines_to_pay[0].payment_date = None
contract_invoice_2.invoice.lines_to_pay[0].save()
contract_invoice_2.invoice.lines_to_pay[0].reload()
contract_invoice_2.invoice.reload()
contract_invoice_2.invoice.lines_to_pay[0].sepa_mandate == \
    contract_invoice_2.invoice.sepa_mandate is None
# #Res# #True
# #Comment# #Restore the payment date
contract_invoice_2.invoice.lines_to_pay[0].payment_date = save_payment_date
contract_invoice_2.invoice.lines_to_pay[0].save()
contract_invoice_2.invoice.lines_to_pay[0].reload()
contract_invoice_2.invoice.reload()

# #Comment# #Delete payments
payment.click('approve')
payment.click('draft')
payment = Payment(payment.id)
payment.delete()

# #Comment# #Deleting the payment will remove the sepa mandate on the line
contract_invoice_2.reload()
contract_invoice_2.invoice.lines_to_pay[0].sepa_mandate is None
# #Res# #True
contract_invoice_2.invoice.sepa_mandate is None
# #Res# #True

# #Comment# #Set billing information sepa mandate to mandate 3
# #Comment# #At the date of the payment_date of the lines_to_pay[1]
# #Comment# #So the sepa_mandate for lines_to_pay[0] must still be None and
# mandate_3 for
# #Comment# #the lines_to_pay[1]
billing_information_no_sepa_2 = BillingInformation(
        date=contract_2_invoice_2.invoice.lines_to_pay[1].payment_date,
        billing_mode=monthly_percent,
        payment_term=monthly_percent.allowed_payment_terms[0],
        direct_debit_day=5,
        payer=subscriber2,
        contract=contract2,
        direct_debit=True,
        sepa_mandate=mandate3)
billing_information_no_sepa_2.direct_debit_account = \
    mandate3.account_number.account
billing_information_no_sepa_2.save()

contract2.reload()
contract_2_invoice_2.reload()
contract_2_invoice_2.invoice.lines_to_pay[0].sepa_mandate is None
# #Res# #True
contract_2_invoice_2.invoice.lines_to_pay[1].sepa_mandate.id == mandate3.id
# #Res# #True

# #Comment# #We get the first line to pay after today, which is lines_to_pay[0]
# #Comment# #with no sepa mandate
contract_2_invoice_2.invoice.sepa_mandate is None
# #Res# #True

config._context['client_defined_date'] = \
    contract_2_invoice_2.invoice.lines_to_pay[1].payment_date
ContractInvoice = Model.get('contract.invoice')
contract_2_invoice_2 = ContractInvoice(contract_2_invoice_2.id)
contract_2_invoice_2.invoice.sepa_mandate.id == mandate3.id
# #Res# #True


contract2 = Contract(contract2.id)
monthly_percent = BillingMode(monthly_percent.id)
mandate4 = Mandate(mandate4.id)
future_billing_information = BillingInformation(
    date=contract_2_invoice_2.invoice.lines_to_pay[1].payment_date +
    relativedelta(months=3),
    billing_mode=monthly_percent,
    payment_term=monthly_percent.allowed_payment_terms[0],
    payer=Party(subscriber2.id),
    direct_debit_day=5,
    sepa_mandate=mandate4)
contract2.billing_informations.append(future_billing_information)
future_billing_information.direct_debit_account = \
    mandate4.account_number.account
contract2.save()

create_batch, = IrModel.find([('model', '=', 'account.payment.create')])
launcher = Wizard('batch.launcher')
launcher.form.batch = create_batch
launcher.form.treatment_date = \
    contract_2_invoice_2.invoice.lines_to_pay[1].payment_date
for i in xrange(0, len(launcher.form.parameters)):
    if launcher.form.parameters[i].code == 'journal_methods':
        launcher.form.parameters[i].value = 'sepa'
    elif launcher.form.parameters[i].code == 'payment_kind':
        launcher.form.parameters[i].value = 'receivable'
launcher.execute('process')
contract_2_invoice_2.reload()

# #Comment# #A payment should be created
Payment = Model.get('account.payment')
payments = Payment.find([('line', 'in',
            [x.id for x in contract_2_invoice_2.invoice.lines_to_pay])])
all([p.state == 'approved' for p in payments])
# #Res# #True
len(payments) == 2
# #Res# #True

# Creating the two payments at the lines_to_pay[1].payment_date gives us
# 2 payments with the same mandate: mandate3 coming from the
# billing_information at date lines_to_pay[1].payment_date.
payments[0].sepa_mandate == payments[1].sepa_mandate == mandate3
# #Res# #True

# #Comment# #Run the batch in the future to process payments at the
# #Comment# #future_billing_information.date + 3 days date.
# #Comment# #Payment date on lines must be re-set and so on, the sepa_mandate
# #Comment# # on the invoice line.
future_date = future_billing_information.date + relativedelta(days=3)
config._context['client_defined_date'] = future_date

launcher = Wizard('batch.launcher')
process_batch, = IrModel.find([('model', '=', 'account.payment.process')])
launcher.form.batch = process_batch
launcher.form.treatment_date = future_date

for i in xrange(0, len(launcher.form.parameters)):
    if launcher.form.parameters[i].code == 'journal_methods':
        launcher.form.parameters[i].value = 'sepa'
    elif launcher.form.parameters[i].code == 'payment_kind':
        launcher.form.parameters[i].value = 'receivable'
launcher.form.parameters.append(BatchParameter(code='cache_size',
        value='100'))

launcher.execute('process')

payments = Payment.find([('line', 'in',
            [x.id for x in contract_2_invoice_2.invoice.lines_to_pay])])
all([x.state == 'processing' for x in payments])
# #Res# #True

# #Comment# #Despite the sepa_mandate changed on the future billing info,
# #Comment# #the sepa mandate on the payment should be still the mandate3.
# #Comment# #This is the expected behavior.
all([x.sepa_mandate == mandate3 for x in payments])
# #Res# #True
