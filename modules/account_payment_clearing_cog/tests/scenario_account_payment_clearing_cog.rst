=========================
Payment Clearing Scenario
=========================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.country_cog.tests.tools import create_country
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from.trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Install account_payment_clearing::

    >>> _ = activate_modules(['account_payment_clearing_cog',
    ...         'account_statement'])

Create country::

    >>> _ = create_country()

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
    >>> payable = accounts['payable']
    >>> cash = accounts['cash']

    >>> Account = Model.get('account.account')
    >>> bank_clearing = Account(name='Bank Clearing', type=payable.type,
    ...     reconcile=True, deferral=True, parent=payable.parent)
    >>> bank_clearing.kind = 'other'  # Warning : on_change_parent !
    >>> bank_clearing.save()

    >>> Journal = Model.get('account.journal')
    >>> expense, = Journal.find([('code', '=', 'EXP')])

Create payment journal::

    >>> PaymentJournal = Model.get('account.payment.journal')
    >>> payment_journal = PaymentJournal(name='Manual',
    ...     process_method='manual', clearing_journal=expense,
    ...     clearing_account=bank_clearing, post_clearing_move=True)
    >>> payment_journal.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

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
    >>> process_payment.execute('process')
    >>> payment.reload()
    >>> payment.state
    u'processing'

Succeed payment::

    >>> payment.click('succeed')
    >>> payment.state
    u'succeeded'
    >>> payment.clearing_move.state
    u'posted'
    >>> clearing_move = payment.clearing_move
    >>> payable.reload()
    >>> payable.balance
    Decimal('-20.00')
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('-30.00')
    >>> payment.line.reconciliation

Fail payment::

    >>> payment.click('fail')
    >>> payment.state
    u'failed'
    >>> payment.clearing_move
    >>> payment.line.reconciliation
    >>> payable.reload()
    >>> payable.balance
    Decimal('-50.00')
    >>> bank_clearing.reload()
    >>> bank_clearing.balance
    Decimal('0.00')
    >>> cancel_move, = Move.find([('origin', '=',
    ...     'account.move,%s' % clearing_move.id)])
    >>> cancel_move.state
    u'posted'
