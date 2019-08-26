# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Payment Creation
# #Comment# #Imports
import datetime
from proteus import Model, Wizard
from decimal import Decimal
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts

# #Comment# #Install Modules
config = activate_modules(['account_payment_cog'])

# #Comment# #Create currency
currency = get_currency(code='EUR')

# #Comment# #Create Company
_ = create_company(currency=currency)
company = get_company()

# #Comment# #Create fiscal year
fiscalyear = create_fiscalyear(company)
fiscalyear.click('create_period')
period = fiscalyear.periods[0]

# #Comment# #Create fiscal year
_ = create_chart(company)
accounts = get_accounts(company)
receivable = accounts['receivable']
revenue = accounts['revenue']

# #Comment# #Create Party
party = create_party_person()

# #Comment# #Some Import
Journal = Model.get('account.journal')
Move = Model.get('account.move')
MoveLine = Model.get('account.move.line')
User = Model.get('res.user')
Warning = Model.get('res.user.warning')
Payment = Model.get('account.payment')
Reconciliation = Model.get('account.move.reconciliation')


# #Comment# #Create Payment Journal
PaymentJournal = Model.get('account.payment.journal')
journal = PaymentJournal()
journal.name = 'Manual'
journal.company = company
journal.currency = currency
journal.process_method = 'manual'
journal.save()


def create_move_line(amount):
    move = Move()
    move.period = period
    move.journal, = Journal.find([('code', '=', 'REV')])
    move.date = period.start_date
    revenue_line = move.lines.new()
    revenue_line.account = revenue
    line = move.lines.new()
    line.account = receivable
    line.party = party
    if amount > 0:
        revenue_line.credit = amount
        line.debit = amount
    else:
        revenue_line.debit = abs(amount)
        line.credit = abs(amount)
    move.save()
    move.click('post')
    line, = [l for l in move.lines if l.account == receivable]
    return line


def test_create_payment(origin, expected_kind, lines, expected_amount,
        unpaid_outstanding_lines=None, lines_with_processing_payments=None,
        ignore_unpaid_lines=False):
    create_payment = Wizard('account.payment.creation', origin)
    create_payment.form.free_motive = True
    create_payment.form.description = "test"
    create_payment.form.payment_date = datetime.date.today()
    create_payment.form.journal = journal
    create_payment.form.ignore_unpaid_lines = ignore_unpaid_lines
    assert create_payment.form.party == party
    assert create_payment.form.kind == expected_kind
    assert create_payment.form.total_amount == expected_amount
    if unpaid_outstanding_lines:
        assert sorted(create_payment.form.unpaid_outstanding_lines,
            key=lambda x: x.id) == sorted(unpaid_outstanding_lines,
            key=lambda x: x.id)
    if lines_with_processing_payments:
        lines_with_processing_payments.sort(key=lambda x: x.id)
        assert sorted(create_payment.form.lines_with_processing_payments,
            key=lambda x: x.id) == sorted(lines_with_processing_payments,
            key=lambda x: x.id)

    warning = Warning()
    warning.always = False
    warning.user = User(1)
    warning.name = 'updating_payment_date_%s' % ('account.move.line,' +
        str(lines[0].id))
    warning.save()

    create_payment.execute('create_payments')

    payment, = Payment.find([('line', '=', lines[-1].id)])
    assert payment.kind == expected_kind
    assert payment.amount == expected_amount
    return payment


def reset_payment_date(line):
    line.reload()
    line.payment_date = None
    line.save()


def set_payment_date(line):
    line.reload()
    line.payment_date = datetime.date.today()
    line.save()


def delete_payment(payment):
    payment.click('draft')
    Payment.delete([payment])


debit = Decimal(42)
debit_line = create_move_line(debit)
delete_payment(test_create_payment(origin=[party], expected_kind='receivable',
        lines=[debit_line], expected_amount=debit))

credit = Decimal(20)
credit_line = create_move_line(- credit)
delete_payment(test_create_payment(origin=[credit_line],
        expected_kind='payable', lines=[credit_line], expected_amount=credit))

delete_payment(test_create_payment(origin=[party], expected_kind='receivable',
        lines=[debit_line], expected_amount=debit - credit))

credit_2 = Decimal(33)
credit_line_2 = create_move_line(- credit_2)
delete_payment(test_create_payment(origin=[party], expected_kind='payable',
        lines=[credit_line_2, credit_line],
        expected_amount=- debit + credit + credit_2))

# #Comment# #Test Unpaid outstanding amount
debit_2 = Decimal(45)
debit_line_2 = create_move_line(debit_2)

delete_payment(test_create_payment(origin=[credit_line, credit_line_2],
        expected_kind='payable', lines=[credit_line, credit_line_2],
        expected_amount=- debit_2 + credit + credit_2,
        unpaid_outstanding_lines=[debit_line_2]))

# #Comment# #Test Ignore Unpaid outstanding amount
delete_payment(test_create_payment(origin=[credit_line],
        expected_kind='payable', lines=[credit_line],
        expected_amount=credit,
        unpaid_outstanding_lines=[debit_line_2],
        ignore_unpaid_lines=True))

debit_3 = Decimal(99)
debit_line_3 = create_move_line(debit_3)
reset_payment_date(credit_line)
reset_payment_date(credit_line_2)
payment = test_create_payment(origin=[debit_line_3], expected_kind='receivable',
    lines=[debit_line_3], expected_amount=debit_3 + debit_2 - credit - credit_2,
    unpaid_outstanding_lines=[debit_line_2, credit_line, credit_line_2])

set_payment_date(debit_line_2)
set_payment_date(credit_line)
set_payment_date(credit_line_2)

# #Comment# #Test processing_payments_outstanding_amount

debit = Decimal(150)
debit_line = create_move_line(debit)
reconciliation_line = create_move_line(- debit_3)
reconciliation = Reconciliation(date=datetime.date.today(),
    lines=[MoveLine(debit_line_3.id), MoveLine(reconciliation_line.id)])
reconciliation.save()
delete_payment(test_create_payment(origin=[debit_line],
    expected_kind='receivable', lines=[debit_line],
    expected_amount=debit - debit_3,
    lines_with_processing_payments=[debit_line_3]))
