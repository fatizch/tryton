# #Title# #Contract Start Date Endorsement Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from proteus import config, Model, Wizard

from trytond.error import UserWarning
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.account.tests.tools import get_accounts, create_chart
from trytond.modules.currency.tests.tools import get_currency

# #Comment# #Init Database
config = config.set_trytond()
config.pool.test = True
# Useful for updating the tests without having to recreate a db from scratch
# import os
# config = config.set_trytond(
#    database='postgresql://tryton:tryton@localhost:5432/tmp_test',
#    user='admin',
#    language='en_US',
#    password='admin',
#    config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
#        'conf', 'trytond.conf'))

# #Comment# #Install Modules
Module = Model.get('ir.module')
invoice_module = Module.find([('name', '=', 'contract_insurance_invoice')])[0]
Module.install([invoice_module.id], config.context)
wizard = Wizard('ir.module.install_upgrade')
wizard.execute('upgrade')

# #Comment# #Get Models
Account = Model.get('account.account')
AccountInvoice = Model.get('account.invoice')
AccountKind = Model.get('account.account.type')
BillingInformation = Model.get('contract.billing_information')
BillingMode = Model.get('offered.billing_mode')
Company = Model.get('company.company')
Contract = Model.get('contract')
ContractInvoice = Model.get('contract.invoice')
ContractPremium = Model.get('contract.premium')
Country = Model.get('country.country')
FiscalYear = Model.get('account.fiscalyear')
Option = Model.get('contract.option')
OptionDescription = Model.get('offered.option.description')
Party = Model.get('party.party')
PaymentTerm = Model.get('account.invoice.payment_term')
PaymentTermLine = Model.get('account.invoice.payment_term.line')
Product = Model.get('offered.product')
Sequence = Model.get('ir.sequence')
SequenceStrict = Model.get('ir.sequence.strict')
SequenceType = Model.get('ir.sequence.type')
User = Model.get('res.user')

# #Comment# #Constants
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
invoice_seq = SequenceStrict(name='2014',
    code='account.invoice', company=company)
invoice_seq.save()
fiscalyear.out_invoice_sequence = invoice_seq
fiscalyear.in_invoice_sequence = invoice_seq
fiscalyear.out_credit_note_sequence = invoice_seq
fiscalyear.in_credit_note_sequence = invoice_seq
fiscalyear.save()
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
coverage = OptionDescription()
coverage.company = company
coverage.currency = currency
coverage.name = u'Test Coverage'
coverage.code = u'test_coverage'
coverage.start_date = product_start_date
coverage.account_for_billing = product_account
coverage.save()

_ = create_chart(company)
accounts = get_accounts(company)
# #Comment# #Create Contract Fee
Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
AccountProduct = Model.get('product.product')
Template = Model.get('product.template')
template = Template()
template.name = 'contract Fee Template'
template.default_uom = unit
template.account_expense = accounts['expense']
template.account_revenue = accounts['revenue']
template.type = 'service'
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.save()
fee_product = AccountProduct()
fee_product.name = 'contract Fee Product'
fee_product.template = template
fee_product.save()
Fee = Model.get('account.fee')
contract_fee = Fee()
contract_fee.name = 'contract Fee'
contract_fee.code = 'contract_fee'
contract_fee.frequency = 'at_contract_signature'
contract_fee.type = 'fixed'
contract_fee.amount = Decimal('800.0')
contract_fee.product = fee_product
contract_fee.save()


product = Product()
product.company = company
product.currency = currency
product.name = 'Test Product'
product.code = 'test_product'
product.contract_generator = contract_sequence
product.quote_number_sequence = quote_sequence
product.start_date = product_start_date
product.billing_modes.append(freq_monthly)
product.billing_modes.append(freq_yearly)
product.coverages.append(coverage)
product.fees.append(contract_fee)
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

# #Comment# #Create Test Contract
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.status = 'quote'
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=freq_yearly, payment_term=payment_term))
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')
contract.options[0].premiums.append(ContractPremium(start=contract_start_date,
        amount=Decimal('100'), frequency='once_per_contract',
        account=product_account, rated_entity=coverage))
contract.premiums.append(ContractPremium(start=contract_start_date,
        amount=Decimal('15'), frequency='monthly', account=product_account,
        rated_entity=product))
contract.premiums.append(ContractPremium(
        start=contract_start_date + datetime.timedelta(days=40),
        amount=Decimal('20'), frequency='yearly', account=product_account,
        rated_entity=coverage))
contract.save()

all_invoices = ContractInvoice.find([('contract', '=', contract.id)])
len(all_invoices)
# #Res# #1
all_invoices[0].invoice.state
# #Res# #u'posted'

# #Comment# #Test invoicing
Contract.first_invoice([contract.id], config.context)
all_invoices = ContractInvoice.find([('contract', '=', contract.id)])
# 2 is for : non periodic invoice + a one year difference means two invoices
len(all_invoices) == 2 + relativedelta(datetime.date.today(),
    contract.start_date).years
# #Res# #True

first_invoice = sorted(ContractInvoice.find([('contract', '=', contract.id),
            ('invoice.state', '=', 'validated')]), key=lambda x: x.start)[0]
first_invoice.invoice.total_amount
# #Res# #Decimal('297.81')
[(x.rec_name, x.unit_price, x.coverage_start, x.coverage_end)
    for x in sorted(first_invoice.invoice.lines, key=lambda x: x.unit_price)
    ] == [
    (u'1', Decimal('17.81'),
        datetime.date(2014, 5, 20), datetime.date(2015, 4, 9)),
    (u'Test Coverage', Decimal('100.00'),
        datetime.date(2014, 4, 10), datetime.date(2015, 4, 9)),
    (u'1', Decimal('180.00'),
        datetime.date(2014, 4, 10), datetime.date(2015, 4, 9)),
    ]
# #Res# #True
Contract.first_invoice([contract.id], config.context)
all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
            ('invoice.state', '=', 'validated')]),
    key=lambda x: x.invoice.start)


# Cannot use try catch directly in a docttest :'(
def test_posting(ids_to_test):
    try:
        AccountInvoice.post(ids_to_test, config.context)
        raise Exception('Failed example, expected to raise UserWarning')
    except UserWarning:
        pass

test_posting([all_invoices[-1].invoice.id])
AccountInvoice.post([all_invoices[0].invoice.id], config.context)
all_invoices[0].invoice.state
# #Res# #u'posted'
Contract.first_invoice([contract.id], config.context)
all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id)]),
    key=lambda x: (x.start or datetime.date.min, x.create_date))
# 3 is for : non periodic invoice + a one year difference means two invoices +
# one of the two was posted, so recalling first_invoice canceled it
len(all_invoices) == 3 + relativedelta(datetime.date.today(),
    contract.start_date).years
# #Res# #True
all_invoices[0].invoice.total_amount
# #Res# #Decimal('800.00')
all_invoices[0].invoice.state
# #Res# #u'posted'
all_invoices[1].invoice.state
# #Res# #u'cancel'
all_invoices[2].invoice.state
# #Res# #u'validated'

# #Comment# #Test option declined
contract = Contract(contract.id)
option_id = contract.options[0].id
Option.delete([Option(option_id)])
Option(option_id).status
# #Res# #u'declined'
contract = Contract(contract.id)
len(contract.options)
# #Res# #0
len(contract.declined_options)
# #Res# #1
