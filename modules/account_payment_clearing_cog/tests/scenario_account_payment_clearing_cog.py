# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Payment Clearing Scenario
# #Comment# #Imports
import datetime
from decimal import Decimal
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
today = datetime.date.today()

# #Comment# #Install account_payment_clearing
_ = activate_modules(['account_payment_clearing_cog',
        'account_statement'])

# #Comment# #Create country
_ = create_country()

# #Comment# #Create company
_ = create_company()
company = get_company()

# #Comment# #Create fiscal year
fiscalyear = set_fiscalyear_invoice_sequences(
    create_fiscalyear(company))
fiscalyear.click('create_period')

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)
receivable = accounts['receivable']
payable = accounts['payable']
cash = accounts['cash']

Account = Model.get('account.account')
bank_clearing = Account(name='Bank Clearing', type=payable.type,
    reconcile=True, deferral=True, parent=payable.parent)
bank_clearing.kind = 'other'  # Warning : on_change_parent !
bank_clearing.save()

Journal = Model.get('account.journal')
expense, = Journal.find([('code', '=', 'EXP')])

# #Comment# #Create payment journal
PaymentJournal = Model.get('account.payment.journal')
payment_journal = PaymentJournal(name='Manual',
    process_method='manual', clearing_journal=expense,
    clearing_account=bank_clearing, post_clearing_move=True)
payment_journal.save()

# #Comment# #Create parties

Party = Model.get('party.party')
supplier = Party(name='Supplier')
supplier.save()

# #Comment# #Create payable move
Move = Model.get('account.move')
move = Move()
move.journal = expense
line = move.lines.new(account=payable, party=supplier,
    credit=Decimal('50.00'))
line = move.lines.new(account=expense, debit=Decimal('50.00'))
move.click('post')
payable.reload()
payable.balance
# #Res# #Decimal('-50.00')

# #Comment# #Partially pay the line
Payment = Model.get('account.payment')
line, = [l for l in move.lines if l.account == payable]
pay_line = Wizard('account.move.line.pay', [line])
pay_line.form.journal = payment_journal
pay_line.execute('start')
payment, = Payment.find()
payment.amount = Decimal('30.0')
payment.click('approve')
payment.state
# #Res# #'approved'
process_payment = Wizard('account.payment.process', [payment])
process_payment.execute('pre_process')
payment.reload()
payment.state
# #Res# #'processing'

# #Comment# #Succeed payment
payment.click('succeed')
payment.state
# #Res# #'succeeded'
payment.clearing_move.state
# #Res# #'posted'
clearing_move = payment.clearing_move
payable.reload()
payable.balance
# #Res# #Decimal('-20.00')
bank_clearing.reload()
bank_clearing.balance
# #Res# #Decimal('-30.00')
payment.line.reconciliation

# #Comment# #Fail payment
payment.click('fail')
payment.state
# #Res# #'failed'
payment.clearing_move
payment.line.reconciliation
payable.reload()
payable.balance
# #Res# #Decimal('-50.00')
bank_clearing.reload()
bank_clearing.balance
# #Res# #Decimal('0.00')
cancel_move, = Move.find([('origin', '=',
    'account.move,%s' % clearing_move.id)])
cancel_move.state
# #Res# #'posted'
