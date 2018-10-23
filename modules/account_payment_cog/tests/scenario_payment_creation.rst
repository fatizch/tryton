=================
Payment Creation
=================

Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from decimal import Decimal
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.party_cog.tests.tools import create_party_person
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install Modules::

    >>> config = activate_modules(['account_payment_cog',
    ...     'account_payment_clearing_cog'])

Create currency::

    >>> currency = get_currency(code='EUR')

Create Company::

    >>> _ = create_company(currency=currency)
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create fiscal year::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']

Create Party::

    >>> party = create_party_person()

Some Import::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> MoveLine = Model.get('account.move.line')
    >>> User = Model.get('res.user')
    >>> Warning = Model.get('res.user.warning')
    >>> Payment = Model.get('account.payment')
    >>> Reconciliation = Model.get('account.move.reconciliation')

Create Payment Journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> journal = PaymentJournal()
    >>> journal.name = 'Manual'
    >>> journal.company = company
    >>> journal.currency = currency
    >>> journal.process_method = 'manual'
    >>> journal.save()
    >>> def create_move_line(amount):
    ...     move = Move()
    ...     move.period = period
    ...     move.journal, = Journal.find([('code', '=', 'REV')])
    ...     move.date = period.start_date
    ...     revenue_line = move.lines.new()
    ...     revenue_line.account = revenue
    ...     line = move.lines.new()
    ...     line.account = receivable
    ...     line.party = party
    ...     if amount > 0:
    ...         revenue_line.credit = amount
    ...         line.debit = amount
    ...     else:
    ...         revenue_line.debit = abs(amount)
    ...         line.credit = abs(amount)
    ...     move.save()
    ...     move.click('post')
    ...     line, = [l for l in move.lines if l.account == receivable]
    ...     return line
    >>> def test_create_payment(origin, party, kind, line0, payment_line, total_amount,
    ...         payment_amount, and_delete=True):
    ...     create_payment = Wizard('account.payment.creation', origin)
    ...     create_payment.form.free_motive = True
    ...     create_payment.form.description = "test"
    ...     create_payment.form.payment_date = datetime.date.today()
    ...     create_payment.form.journal = journal
    ...     assert create_payment.form.party == party
    ...     assert create_payment.form.kind == kind
    ...     assert create_payment.form.total_amount == total_amount
    ...     warning = Warning()
    ...     warning.always = False
    ...     warning.user = User(1)
    ...     warning.name = 'updating_payment_date_%s' % ('account.move.line,' +
    ...         str(line0.id))
    ...     warning.save()
    ...     create_payment.execute('create_payments')
    ...     payment, = Payment.find([('line', '=', payment_line)])
    ...     assert payment.kind == kind
    ...     assert payment.amount == payment_amount
    ...     if and_delete:
    ...         payment.state = 'draft'
    ...         payment.save()
    ...         Payment.delete([payment])
    ...     else:
    ...         return payment
    >>> def reset_payment_date(line):
    ...     line.reload()
    ...     line.payment_date = None
    ...     line.save()
    >>> def set_payment_date(line):
    ...     line.reload()
    ...     line.payment_date = datetime.date.today()
    ...     line.save()
    >>> debit = Decimal(42)
    >>> debit_line = create_move_line(debit)
    >>> test_create_payment([party], party, 'receivable', debit_line, debit_line, debit,
    ...     debit)
    >>> credit = Decimal(20)
    >>> credit_line = create_move_line(- credit)
    >>> test_create_payment([credit_line], party, 'payable', credit_line, credit_line,
    ...     credit, credit)
    >>> test_create_payment([party], party, 'receivable', debit_line, debit_line,
    ...     debit - credit, debit - credit)
    >>> credit_2 = Decimal(33)
    >>> credit_line_2 = create_move_line(- credit_2)
    >>> test_create_payment([party], party, 'payable', credit_line_2, credit_line,
    ...     - debit + credit + credit_2, - debit + credit + credit_2)

Test Unpaid outstanding amount::

    >>> debit_2 = Decimal(45)
    >>> debit_line_2 = create_move_line(debit_2)
    >>> test_create_payment([credit_line, credit_line_2], party, 'payable', credit_line,
    ...     credit_line_2, credit + credit_2, - debit_2 + credit + credit_2)
    >>> debit_3 = Decimal(99)
    >>> debit_line_3 = create_move_line(debit_3)
    >>> reset_payment_date(credit_line)
    >>> reset_payment_date(credit_line_2)
    >>> payment = test_create_payment([debit_line_3], party, 'receivable',
    ...     debit_line_3, debit_line_3, debit_3, debit_3 + debit_2 - credit - credit_2,
    ...     and_delete=False)
    >>> set_payment_date(debit_line_2)
    >>> set_payment_date(credit_line)
    >>> set_payment_date(credit_line_2)

Test processing_payments_outstanding_amount::

    >>> debit = Decimal(150)
    >>> debit_line = create_move_line(debit)
    >>> reconciliation_line = create_move_line(- debit_3)
    >>> reconciliation = Reconciliation(date=datetime.date.today(),
    ...     lines=[MoveLine(debit_line_3.id), MoveLine(reconciliation_line.id)])
    >>> reconciliation.save()
    >>> test_create_payment([debit_line], party, 'receivable', debit_line, debit_line,
    ...     debit, debit - debit_3)
