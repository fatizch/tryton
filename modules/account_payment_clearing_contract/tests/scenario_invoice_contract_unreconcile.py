# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Insurance Invoice Unreconcile  Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
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
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.premium.tests.tools import add_premium_rules


# #Comment# #Init Database
# Useful for updating the tests without having to recreate a db from scratch
# import os
# from proteus import config
# config = config.set_trytond(
#    database='postgresql://postgres:postgres@localhost:5432/tmp_test',
#    user='admin',
#    config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'workspace',
#        'conf', 'trytond.conf'))
#

# #Comment# #Install Modules
config = activate_modules(['account_statement_contract',
    'account_payment_clearing_contract'])

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

# #Comment# #Create chart of accounts
Account = Model.get('account.account')
_ = create_chart(company)
accounts = get_accounts(company)
cash = accounts['cash']
receivable = accounts['receivable']
payable = accounts['payable']
bank_clearing = Account(name='Bank Clearing', type=payable.type,
    reconcile=True, deferral=True, parent=payable.parent)
bank_clearing.kind = 'other'  # Warning : on_change_parent !
bank_clearing.save()
Journal = Model.get('account.journal')
expense, = Journal.find([('code', '=', 'EXP')])

# #Comment# #Create Payment Journal
PaymentJournal = Model.get('account.payment.journal')
payment_journal = PaymentJournal(name='Manual',
    process_method='manual', clearing_journal=expense,
    clearing_account=bank_clearing, post_clearing_move=True)
payment_journal.save()

# #Comment# #Create Fee
AccountKind = Model.get('account.account.type')
Product = Model.get('product.product')
Template = Model.get('product.template')
template = Template()
template.name = 'product template'
template.type = 'service'
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.save()
Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
product_product = Product()
product_product.name = 'Product'
product_product.template = template
product_product.default_uom = template.default_uom
product_product.payment_journal = payment_journal
product_product.type = 'service'
product_product.save()
Fee = Model.get('account.fee')
fee = Fee()
fee.name = 'Test Fee'
fee.code = 'test_fee'
fee.type = 'fixed'
fee.amount = Decimal('22')
fee.frequency = 'once_per_invoice'
fee.product = product_product
fee.save()

# #Comment# #Create Product
product = init_product()
product = add_quote_number_generator(product)
product = add_premium_rules(product)
product = add_invoice_configuration(product, accounts)
product = add_insurer_to_product(product)
product.save()


# #Comment# #Create Subscriber
subscriber = create_party_person()

# #Comment# #Create Contract
contract_start_date = datetime.date.today() - relativedelta(months=3)
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=product.billing_modes[0],
        payment_term=product.billing_modes[0].allowed_payment_terms[0]))
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')
contract.billing_information.direct_debit is False
# #Res# #True


# #Comment# #Create two invoices of 100.00
invoice_wizard = Wizard('contract.do_invoice', models=[contract])
invoice_wizard.form.up_to_date = contract_start_date + relativedelta(months=1)
invoice_wizard.execute('invoice')

ContractInvoice = Model.get('contract.invoice')
AccountInvoice = Model.get('account.invoice')

# #Comment# #Post the invoices of 100.00
invoices = ContractInvoice.find([('contract', '=', contract.id)])
AccountInvoice.post([x.id for x in invoices], config.context)
invoices = list(reversed([x.invoice for x in invoices]))

StatementJournal = Model.get('account.statement.journal')
Statement = Model.get('account.statement')
StatementLine = Model.get('account.statement.line')
Sequence = Model.get('ir.sequence')
AccountJournal = Model.get('account.journal')

sequence = Sequence(name='sequence',
    code='account.journal',
    company=company)

# #Comment# #Create the statement sequence
statement_sequence = Sequence(name='Statement Sequence',
    code='statement',
    company=company)
sequence.save()
statement_sequence.save()


# #Comment# #Create the account journal
account_journal = AccountJournal(name='Statement',
    type='statement',
    credit_account=cash,
    debit_account=cash,
    sequence=sequence
    )
account_journal.save()

# #Comment# #Create the statement journal
statement_journal = StatementJournal(name='Test',
    journal=account_journal,
    validation='balance',
    sequence=statement_sequence,
    process_method='cheque'
    )
statement_journal.save()

# #Comment# #Create a statement of 180.00 for an invoice of 100.00
statement = Statement(name='test',
    journal=statement_journal,
    start_balance=Decimal('0'),
    end_balance=Decimal('180')
    )
statement_line = StatementLine()
statement.lines.append(statement_line)
statement.lines[0].number = '0001'
statement.lines[0].description = 'description'
statement.lines[0].date = datetime.date.today()
statement.lines[0].amount = Decimal('180')
statement.lines[0].party = subscriber
statement.lines[0].contract = contract
statement.lines[0].party_payer = subscriber
statement.lines[0].invoice = None
statement.save()

statement.click('validate_statement')
statement.click('post')
statement_line = statement.lines[0]

MoveLine = Model.get('account.move.line')

invoices[0].total_amount
# #Res# #Decimal('100.00')
invoices[1].total_amount
# #Res# #Decimal('100.00')

# #Comment# #Reconcile the statement line with line to pay on the first invoice
# #Comment# #There is an overdue of 80.00 which is set on the contract
reconcile_wiz = Wizard('account.reconcile')
line_to_pay = invoices[0].lines_to_pay[0]
overdue_line = None
for move_line in statement_line.move.lines:
    if move_line.amount == Decimal('-180'):
        overdue_line = move_line
        break

for line in [MoveLine(line_to_pay.id), MoveLine(overdue_line.id)]:
    reconcile_wiz.form.lines.append(line)

reconcile_wiz.form.remaining_repartition_method = 'set_on_contract'
reconcile_wiz.execute('reconcile')
invoices[0].state == 'paid'
# #Res# #True
invoices[1].state == 'posted'
# #Res# #True

invoices[0].amount_to_pay_today
# #Res# #Decimal('0.0')

# #Comment# #The balance should be 20 (100 - (180 - 100))
contract.balance_today == invoices[0].total_amount - Decimal('80.00')
# #Res# #True

# #Comment# #Create payment which pay the rest of the second invoice
Payment = Model.get('account.payment')
line, = invoices[1].lines_to_pay
pay_line = Wizard('account.payment.creation', [line])
pay_line.form.description = 'Payment'
pay_line.form.journal = payment_journal
pay_line.execute('create_payments')
payment, = Payment.find()
payment.amount
# #Res# #Decimal('20.00')
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('pre_process')
payment.reload()
payment.click('succeed')

invoices[1].reload()
invoices[1].state == 'paid'
# #Res# #True

invoices[1].amount_to_pay_today
# #Res# #Decimal('0.0')

# #Comment# #Unreconcile the statement line of 180. All reconciliations should
# #Comment# # be deleted
unreconcile = Wizard('account.move.unreconcile_lines', [overdue_line])
invoices = [x.invoice for x in
    ContractInvoice.find([('contract', '=', contract.id)])]
invoices[0].state == 'posted'
# #Res# #True
invoices[1].state == 'posted'
# #Res# #True

# #Comment# #Each line of the split move should be reconciliated together
# #Comment# # be deleted
Move = Model.get('account.move')
move, = Move.find([('journal.code', '=', 'SPLIT')])
len(list(set([x.reconciliation for x in move.lines]))) == 1
# #Res# #True
