# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Start Date Endorsement Scenario
# #Comment# #Imports
import os
import sys
from proteus import Model, Wizard

import datetime
from subprocess import Popen as popen


from trytond.tests.tools import activate_modules
from trytond.modules.coog_core.test_framework import execute_test_case,\
    switch_user
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.account.tests.tools import create_chart, get_accounts
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.offered_insurance.tests.tools import add_insurer_to_product
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.premium.tests.tools import add_premium_rules
from trytond.modules.contract_insurance_invoice.tests.tools import \
    add_invoice_configuration

from trytond.modules.bank_mobility import batch as bank_mobility

# #Comment# #Install Modules
config = activate_modules('bank_mobility')
# #Comment# #Get Models
IrModel = Model.get('ir.model')
Bank = Model.get('bank')
BankAccount = Model.get('bank.account')
BillingMode = Model.get('offered.billing_mode')
BillingInformation = Model.get('contract.billing_information')
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
Journal = Model.get('account.payment.journal')
Mandate = Model.get('account.payment.sepa.mandate')
Number = Model.get('bank.account.number')
Party = Model.get('party.party')
User = Model.get('res.user')
Endorsement = Model.get('endorsement')

# #Comment# #Constants
today = datetime.date.today()
product_start_date = datetime.date(2014, 1, 1)

# #Comment# #Create country
_ = create_country()

# #Comment# #Create currenct
currency = get_currency(code='EUR')

# #Comment# #Create Company
_ = create_company(currency=currency)

# #Comment# #Reload the context
execute_test_case('authorizations_test_case')
config = switch_user('admin')
company = get_company()

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)


# #Comment# Create Banks
def create_bank(bank_name, bank_bic):
    party_bank = Party()
    party_bank.name = bank_name
    party_bank.save()
    bank = Bank()
    bank.party = party_bank
    bank.bic = bank_bic
    bank.save()
    return bank


bank = create_bank('BNP-Paribas SA', 'BNPAFRPPXXX')
bank2 = create_bank('AXA Banque SA', 'AXABFRPPXXX')
bank3 = create_bank('Caisse d\'Epargne CEPAC', 'CEPAFRPP131')
bank4 = create_bank('Banque de France', 'BDFEFRPPCCT')
bank5 = create_bank('Natixis', 'NATXFRPPXXX')
bank6 = create_bank('BRED Banque Populaire', 'BREDFRPPXXX')
company_account = BankAccount()
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


# #Comment# #Local Methods
def create_party_and_bank_account(last_name, first_name, iban, cur_bank):
    s = create_party_person(last_name, first_name)
    s_acc = BankAccount()
    s_acc.bank = cur_bank
    s_acc.owners.append(s)
    s_acc.currency = currency
    s_acc.number = iban
    s_acc.save()
    return s, s_acc


def create_mandate(party, account, identification, signature_date):
    m = Mandate()
    m.company = company
    m.party = party
    m.account_number = account.numbers[0]
    m.identification = identification
    m.type = 'recurrent'
    m.signature_date = datetime.date(2017, 1, 1)
    m.start_date = datetime.date(2017, 1, 1)
    m.save()
    m.click('request')
    m.click('validate_mandate')
    return m


def create_contract(subscriber, start_date, mandate, contract_number,
        subscriber_account):
    monthly_direct_debit, = BillingMode.find([
            ('code', '=', 'monthly_direct_debit')])
    contract = Contract()
    contract.company = company
    contract = Contract()
    contract.subscriber = subscriber
    contract.start_date = start_date
    contract.product = product
    contract.billing_informations.append(BillingInformation(date=None,
            billing_mode=monthly_direct_debit,
            payment_term=monthly_direct_debit.allowed_payment_terms[0],
            direct_debit_day=5,
            payer=subscriber,
            direct_debit_account=subscriber_account,
            sepa_mandate=mandate
            ))
    contract.contract_number = contract_number
    contract.save()
    Wizard('contract.activate', models=[contract]).execute('apply')
    return contract


# #Comment# #Create Subscriber 1
subscriber, subscriber_account = create_party_and_bank_account(
    'Martin', 'Jean', 'FR76 3000 4000 0312 3456 7890 143', bank)
# #Comment# #Create SEPA mandate 1 and 2
mandate1 = create_mandate(subscriber, subscriber_account,
        'COO11405-0000000260', datetime.date(2017, 1, 1))
mandate2 = create_mandate(subscriber, subscriber_account,
        'COO11405-0000000261', datetime.date(2017, 1, 1))

# #Comment# #Create Contract 1 and 2
contract = create_contract(subscriber, datetime.date(2017, 1, 1), mandate1, '1',
        subscriber_account)
contract2 = create_contract(subscriber, datetime.date(2017, 1, 1), mandate2,
        '2', subscriber_account)

# #Comment# #Create Subscriber 2
subscriber2, subscriber_account2 = create_party_and_bank_account(
    'Mitchell', 'Jacky', 'FR76 1254 8029 9812 3456 7890 161', bank2)
# #Comment# #Create SEPA mandate 3
mandate3 = create_mandate(subscriber2, subscriber_account2,
    'COO11404-0000000262', datetime.date(2017, 1, 1))

# #Comment# #Create Contract 3
contract3 = create_contract(subscriber2, datetime.date(2017, 1, 1), mandate3,
        '3', subscriber_account2)

# #Comment# #Create Subscriber 3
subscriber3, subscriber_account3 = create_party_and_bank_account(
        'Fillon', 'François', 'FR76 1131 5000 0112 3456 7890 138', bank3)


module_file = bank_mobility.__file__
module_folder = os.path.dirname(module_file)

bank_mobility_batch, = IrModel.find([('model', '=', 'bank.mobility')])


def debug_print(to_print):
    print >> sys.stderr, to_print


def import_flow_5(file_name):
    debug_print('testing %s' % file_name)
    launcher = Wizard('batch.launcher')
    launcher.form.batch = bank_mobility_batch
    dir_ = os.path.join(module_folder, 'tests_imports/')
    file_path = dir_ + file_name
    for i in xrange(0, len(launcher.form.parameters)):
        if launcher.form.parameters[i].code == 'in_directory':
            launcher.form.parameters[i].value = file_path
        elif launcher.form.parameters[i].code == 'archive':
            launcher.form.parameters[i].value = dir_
    try:
        launcher.execute('process')
        return
    finally:
        archived = dir_ + 'treated_%s_%s' % (str(today),
            file_name)
        cmd = 'mv %s %s' % (archived, file_path)
        __ = popen(cmd.split())  # NOQA


__ = import_flow_5('flow_5_test.xml')  # NOQA


# #Comment# #Test on bank accounts
orgl_bank_account_number_1, = Number.find([('number_compact', '=',
    'FR7630004000031234567890143')])
orgl_bank_account_number_2, = Number.find([('number_compact', '=',
    'FR7612548029981234567890161')])
orgl_bank_account_number_3, = Number.find([('number_compact', '=',
    'FR7611315000011234567890138')])
updt_bank_account_number_1, = Number.find([('number_compact', '=',
    'FR7630001007941234567890185')])
updt_bank_account_number_2, = Number.find([('number_compact', '=',
    'FR7630007000111234567890144')])
updt_bank_account_number_3, = Number.find([('number_compact', '=',
    'FR7610107001011234567890129')])

(orgl_bank_account_number_1.account.end_date == datetime.date(2017, 9, 30))
# #Res# #True
(orgl_bank_account_number_2.account.end_date == datetime.date(2017, 10, 1))
# #Res# #True
(orgl_bank_account_number_3.account.end_date == datetime.date(2017, 10, 1))
# #Res# #True
(updt_bank_account_number_1.account.start_date == datetime.date(2017, 9, 30))
# #Res# #True
(updt_bank_account_number_2.account.start_date == datetime.date(2017, 10, 1))
# #Res# #True
(updt_bank_account_number_3.account.start_date == datetime.date(2017, 10, 1))
# #Res# #True

# #Comment# #Test on sepa mandates
orgl_sepa_mandate_1, = Mandate.find([('identification', '=',
            'COO11405-0000000260'), ('amendment_of', '=', None)])
orgl_sepa_mandate_2, = Mandate.find([('identification', '=',
            'COO11405-0000000261'), ('amendment_of', '=', None)])
orgl_sepa_mandate_3, = Mandate.find([('identification', '=',
            'COO11404-0000000262'), ('amendment_of', '=', None)])
updt_sepa_mandate_1, = Mandate.find([('identification', '=',
            'COO11405-0000000260'), ('amendment_of', '!=', None)])
updt_sepa_mandate_2, = Mandate.find([('identification', '=',
            'COO11405-0000000261'), ('amendment_of', '!=', None)])
updt_sepa_mandate_3, = Mandate.find([('identification', '=',
            'COO11404-0000000262'), ('amendment_of', '!=', None)])

orgl_sepa_mandate_1 and (orgl_sepa_mandate_1.start_date ==
    datetime.date(2017, 1, 1))
# #Res# #True
orgl_sepa_mandate_2 and (orgl_sepa_mandate_2.start_date ==
    datetime.date(2017, 1, 1))
# #Res# #True
orgl_sepa_mandate_3 and (orgl_sepa_mandate_3.start_date ==
    datetime.date(2017, 1, 1))
# #Res# #True
updt_sepa_mandate_1 and (updt_sepa_mandate_1.start_date ==
    datetime.date(2017, 9, 30))
# #Res# #True
updt_sepa_mandate_2 and (updt_sepa_mandate_2.start_date ==
    datetime.date(2017, 9, 30))
# #Res# #True
updt_sepa_mandate_3 and (updt_sepa_mandate_3.start_date ==
    datetime.date(2017, 10, 1))
# #Res# #True

# #Comment# #Test on Contracts
contract_1, = Contract.find([('contract_number', '=', '1')])
contract_2, = Contract.find([('contract_number', '=', '2')])
contract_3, = Contract.find([('contract_number', '=', '3')])

contract_billing_information_1, = BillingInformation.find([
        ('contract', '=', contract_1.id),
        ('date', '=', datetime.date(2017, 9, 30))])
contract_billing_information_2, = BillingInformation.find([
        ('contract', '=', contract_2.id),
        ('date', '=', datetime.date(2017, 9, 30))])
contract_billing_information_3, = BillingInformation.find([
        ('contract', '=', contract_3.id),
        ('date', '=', datetime.date(2017, 10, 1))])

contract_billing_information_1 and \
    contract_billing_information_1.direct_debit_account == \
    updt_bank_account_number_1.account and \
    contract_billing_information_1.sepa_mandate == updt_sepa_mandate_1
# #Res# #True
contract_billing_information_2 and \
    contract_billing_information_2.direct_debit_account == \
    updt_bank_account_number_1.account and \
    contract_billing_information_2.sepa_mandate == updt_sepa_mandate_2
# #Res# #True
contract_billing_information_3 and \
    contract_billing_information_3.direct_debit_account \
    == updt_bank_account_number_2.account and \
    contract_billing_information_3.sepa_mandate == updt_sepa_mandate_3
# #Res# #True
