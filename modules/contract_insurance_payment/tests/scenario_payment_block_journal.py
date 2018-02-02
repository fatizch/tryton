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
    create_billing_mode
from trytond.modules.account_invoice.tests.tools import create_payment_term
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
config = activate_modules(['contract_insurance_payment', 'batch_launcher',
        'account_payment_sepa_contract'])

# #Comment# #Create country
_ = create_country()

# #Comment# #Create currency
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

Number = Model.get('bank.account.number')
banks = Bank.find([])
Account = Model.get('bank.account')
company_account = Account()
company_account.bank = bank
company_account.owners.append(company.party)
company_account.currency = currency
company_account.number = 'ES8200000000000000000000'
company_account.save()

payment_term = create_payment_term()
payment_term.save()
monthly = create_billing_mode('monthly', payment_term.id)

# #Comment# #Create Payment Journals
BillingMode = Model.get('offered.billing_mode')

Journal = Model.get('account.payment.journal')
journal = Journal()
journal.name = 'Journal'
journal.company = company
journal.currency = currency
journal.process_method = 'sepa'
journal.failure_billing_mode, = BillingMode.find([('code', '=',
    'monthly')])
journal.sepa_payable_flavor = 'pain.001.001.03'
journal.sepa_receivable_flavor = 'pain.008.001.02'
journal.sepa_charge_bearer = 'DEBT'
journal.sepa_bank_account_number = company_account.numbers[0]
journal.save()

Journal2 = Model.get('account.payment.journal')
journal2 = Journal()
journal2.name = 'Journal 2'
journal2.company = company
journal2.currency = currency
journal2.process_method = 'sepa'
journal2.failure_billing_mode, = BillingMode.find([('code', '=',
    'monthly')])
journal2.sepa_payable_flavor = 'pain.001.001.03'
journal2.sepa_receivable_flavor = 'pain.008.001.02'
journal2.sepa_charge_bearer = 'DEBT'
journal2.sepa_bank_account_number = company_account.numbers[0]
journal2.save()

# #Comment# #Create Product 1
product = init_product(name='product_1')
product = add_quote_number_generator(product)
product = add_premium_rules(product)
product.payment_journal = journal
product = add_insurer_to_product(product)
for coverage in product.coverages:
    coverage.name = 'coverage_1'
    coverage.code = 'coverage_1'
    coverage.account_for_billing = Model.get('account.account')(
        accounts['revenue'].id)

product.save()

# #Comment# #Create Product 2
product2 = init_product(name='product_2')
product2 = add_quote_number_generator(product2)
product2 = add_premium_rules(product2)
product2.payment_journal = journal2
product2 = add_insurer_to_product(product2)
for coverage in product2.coverages:
    coverage.name = 'coverage_2'
    coverage.code = 'coverage_2'
    coverage.account_for_billing = Model.get('account.account')(
        accounts['revenue'].id)

product2.save()

Configuration = Model.get('account.configuration')
configuration = Configuration(1)
configuration.save()

AccountJournal = Model.get('account.journal')
expense, = AccountJournal.find([('code', '=', 'EXP')])
# #Comment# #Create Subscriber
subscriber = create_party_person()
subscriber2 = create_party_person(name='other')

subscriber_account = Account()
subscriber_account.bank = bank
subscriber_account.owners.append(subscriber)
subscriber_account.currency = currency
subscriber_account.number = 'BE82068896274468'
subscriber_account.save()

# #Comment# #Create Contract
monthly = BillingMode(monthly.id)
product.billing_modes.append(monthly)
product.save()
monthly = BillingMode(monthly.id)
product2.billing_modes.append(monthly)
product2.save()

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

# #Comment# #Add billing information with monthly billing monde
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=monthly,
        payment_term=monthly.allowed_payment_terms[0],
        payer=subscriber))
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

contract2 = Contract()
contract2.company = company
contract2.subscriber = subscriber
contract2.start_date = contract_start_date
contract2.product = product2
# #Comment# #Remove default billing mode
bool(contract2.billing_informations.pop(0))
# #Res# #True

# #Comment# #Add billing information with monthly billing monde
contract2.billing_informations.append(BillingInformation(date=None,
        billing_mode=monthly,
        payment_term=monthly.allowed_payment_terms[0],
        payer=subscriber))
contract2.contract_number = '987654321'
contract2.save()
Wizard('contract.activate', models=[contract2]).execute('apply')

# #Comment# #Create invoices
until_date = contract_start_date
generate_invoice = Wizard('contract.do_invoice', models=[contract])
generate_invoice.form.up_to_date = until_date
generate_invoice.execute('invoice')
contract.reload()
contract_invoices = contract.invoices

generate_contract_2_invoice = Wizard('contract.do_invoice', models=[contract2])
generate_contract_2_invoice.form.up_to_date = until_date
generate_contract_2_invoice.execute('invoice')
contract_invoices2 = contract2.invoices

len(contract_invoices) == 1
# #Res# #True
len(contract_invoices2) == 1
# #Res# #True

contract_invoice, = contract_invoices
contract_invoice_2, = contract_invoices2

contract_invoice.invoice.click('post')
contract_invoice_2.invoice.click('post')

lines_to_pay = contract_invoice.invoice.lines_to_pay + \
    contract_invoice_2.invoice.lines_to_pay

# #Comment# #Generate payment (error should be raised) because product journals
# are differents
create_payment = Wizard('account.payment.creation', lines_to_pay)  # doctest: +IGNORE_EXCEPTION_DETAIL
# #Hard# #Traceback (most recent call last):
# #Hard# #    ...
# #Hard# #UserError: ...

# #Comment# #Generate Set same product to be able to generate the payments
# #Comment# #But the journal won't be selectable.
product.payment_journal = journal2
product.save()

create_payment = Wizard('account.payment.creation', lines_to_pay)
[x.id for x in create_payment.form.possible_journals] == [journal2.id]
# #Res# #True
create_payment.form.journal == journal2
# #Res# #True

# #Comment# #Remove journals to be able to change payment journal without any
# restrictions
product.payment_journal = None
product2.payment_journal = None
product.save()
product2.save()

create_payment = Wizard('account.payment.creation', lines_to_pay)
len(create_payment.form.possible_journals) == 2
# #Res# #True

# #Comment# #Remove Set the journal on 1 product only: we are able to generate
# the payment but the journal won't be selectable
product2.payment_journal = journal
product2.save()

create_payment = Wizard('account.payment.creation', lines_to_pay)
[x.id for x in create_payment.form.possible_journals] == [journal.id]
# #Res# #True
