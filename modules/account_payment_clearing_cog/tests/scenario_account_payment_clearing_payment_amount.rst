=================================
Payment Clearing Amount Scenario
=================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()
    >>> first = today + relativedelta(day=1)

Install account_payment_clearing and account_statement::

    >>> config = activate_modules(['account_payment_clearing_cog',
    ...         'account_statement'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']
    >>> Account = Model.get('account.account')
    >>> bank_clearing = Account(parent=payable.parent)
    >>> bank_clearing.name = 'Bank Clearing'
    >>> bank_clearing.type = payable.type
    >>> bank_clearing.reconcile = True
    >>> bank_clearing.deferral = True
    >>> bank_clearing.kind = 'other'
    >>> bank_clearing.save()
    >>> Journal = Model.get('account.journal')
    >>> expense, = Journal.find([('code', '=', 'EXP')])
    >>> revenue_journal, = Journal.find([('code', '=', 'REV')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual', clearing_journal=expense,
    ...     clearing_account=bank_clearing)
    >>> payment_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create payable move::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.journal = expense
    >>> line = move.lines.new(account=payable, party=supplier,
    ...     credit=Decimal('50.00'))
    >>> line = move.lines.new(account=expense, debit=Decimal('50.00'))
    >>> move.click('post')
    >>> payable.reload()
    >>> payable.balance
    Decimal('-50.00')

Partially pay the line::

    >>> Payment = Model.get('account.payment')
    >>> line, = [l for l in move.lines if l.account == payable]
    >>> pay_line = Wizard('account.move.line.pay', [line])
    >>> pay_line.form.journal = payment_journal
    >>> pay_line.execute('start')
    >>> payment, = Payment.find()
    >>> payment.amount = Decimal('30.0')
    >>> payment.click('approve')
    >>> payment.state
    u'approved'
    >>> process_payment = Wizard('account.payment.process', [payment])
    >>> process_payment.execute('pre_process')
    >>> payment.reload()
    >>> payment.state
    u'processing'
    >>> line.reload()
    >>> line.payment_amount
    Decimal('20.00')

Succeed payment::

    >>> succeed = Wizard('account.payment.succeed', [payment])
    >>> succeed.form.date == today
    True
    >>> succeed.form.date = first
    >>> succeed.execute('succeed')
    >>> payment.state
    u'succeeded'
    >>> payment.clearing_move.date == first
    True
    >>> payment.clearing_move.state
    u'posted'
    >>> payable.reload()
    >>> payable.balance
    Decimal('-20.00')
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('-30.00')
    >>> payment.line.reconciliation
    >>> line_from_clearing, = [l for l in payment.clearing_move.lines
    ...     if l.account.name == 'Main Payable']

Create another payable move::

    >>> Move = Model.get('account.move')
    >>> move2 = Move()
    >>> move2.journal = expense
    >>> line2a = move2.lines.new(account=payable, party=supplier,
    ...     credit=Decimal('30.00'))
    >>> line2a = move2.lines.new(account=expense, debit=Decimal('30.00'))
    >>> move2.click('post')
    >>> line_from_move2, = [l for l in move2.lines if l.account.name == 'Main Payable']

Reconcile Account::

    >>> reconcile_accounts = Wizard('account.reconcile')
    >>> wizard_lines = reconcile_accounts.form.lines
    >>> assert len(wizard_lines) == 2
    >>> assert line_from_move2 in wizard_lines
    >>> assert line_from_clearing in wizard_lines
    >>> reconcile_accounts.form.journal = None
    >>> reconcile_accounts.form.description = 'test reconciliation'
    >>> reconcile_accounts.execute('reconcile')
    >>> reconciliation, = Model.get('account.move.reconciliation').find([])
    >>> assert len(reconciliation.lines) == 2
    >>> assert line_from_move2 in reconciliation.lines
    >>> assert line_from_clearing in reconciliation.lines

Check Payment Amount::

    >>> move.reload()
    >>> line_from_move, = [l for l in move.lines if l.account == payable]
    >>> line_from_move.payment_amount
    Decimal('50.00')
