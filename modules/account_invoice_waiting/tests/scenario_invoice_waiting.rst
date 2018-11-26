==============================
 Test account invoice waiting
==============================

 Init::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.coog_core.test_framework import execute_test_case, \
    ...     switch_user
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, create_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Set date::

    >>> today = datetime.date.today()

Install Modules::

    >>> config = activate_modules('account_invoice_waiting')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> tax_identifier = company.party.identifiers.new()
    >>> tax_identifier.type = 'eu_vat'
    >>> tax_identifier.code = 'BE0897290877'
    >>> company.party.save()
    >>> execute_test_case('authorizations_test_case')
    >>> config = switch_user('financial_user')
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create waiting account::

    >>> _ = create_chart(company)
    >>> WaitingAccount = Model.get('account.account')
    >>> WaitingAccountKind = Model.get('account.account.type')
    >>> waiting_account_kind = WaitingAccountKind()
    >>> waiting_account_kind.name = 'Waiting Account Kind'
    >>> waiting_account_kind.company = company
    >>> waiting_account_kind.save()
    >>> waiting_account = WaitingAccount()
    >>> waiting_account.name = 'Waiting Account'
    >>> waiting_account.company = company
    >>> waiting_account.code = 'waiting_account'
    >>> waiting_account.kind = 'other'
    >>> waiting_account.type = waiting_account_kind
    >>> waiting_account.save()

Create base account::

    >>> BaseAccount = Model.get('account.account')
    >>> BaseAccountKind = Model.get('account.account.type')
    >>> base_account_kind = BaseAccountKind()
    >>> base_account_kind.name = 'Base Account Kind'
    >>> base_account_kind.company = company
    >>> base_account_kind.save()
    >>> base_account = BaseAccount()
    >>> base_account.name = 'Base Account'
    >>> base_account.company = company
    >>> base_account.code = 'base_account'
    >>> base_account.kind = 'other'
    >>> base_account.type = base_account_kind
    >>> base_account.save()

Create chart of accounts::

    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> waiting_account.waiting_for_account = accounts['revenue']
    >>> waiting_account.save()
    >>> revenue_without_waiting = base_account
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']
    >>> account_cash = accounts['cash']

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.save()
    >>> invoice_base_code = create_tax_code(tax, 'base', 'invoice')
    >>> invoice_base_code.save()
    >>> invoice_tax_code = create_tax_code(tax, 'tax', 'invoice')
    >>> invoice_tax_code.save()
    >>> credit_note_base_code = create_tax_code(tax, 'base', 'credit')
    >>> credit_note_base_code.save()
    >>> credit_note_tax_code = create_tax_code(tax, 'tax', 'credit')
    >>> credit_note_tax_code.save()

Set Cash journal::

    >>> Journal = Model.get('account.journal')
    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = account_cash
    >>> payment_method.debit_account = account_cash
    >>> payment_method.save()

Create Write-Off journal::

    >>> Sequence = Model.get('ir.sequence')
    >>> sequence_journal, = Sequence.find([('code', '=', 'account.journal')])
    >>> journal_writeoff = Journal(
    ...     name='Write-Off',
    ...     type='write-off',
    ...     sequence=sequence_journal)
    >>> journal_writeoff.save()
    >>> WriteOff = Model.get('account.move.reconcile.write_off')
    >>> writeoff = WriteOff()
    >>> writeoff.name = 'Write Off Journal'
    >>> writeoff.journal = journal_writeoff
    >>> writeoff.credit_account = waiting_account
    >>> writeoff.debit_account = expense
    >>> writeoff.save()
    >>> journal_writeoff.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> ProductCategory = Model.get('product.category')
    >>> account_category_waiting = ProductCategory(name="Account Category Waiting")
    >>> account_category_waiting.accounting = True
    >>> account_category_waiting.account_expense = expense
    >>> account_category_waiting.account_revenue = waiting_account
    >>> account_category_waiting.customer_taxes.append(tax)
    >>> account_category_waiting.code = 'account_category_waiting'
    >>> account_category_waiting.save()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.cost_price = Decimal('25')
    >>> template.account_category = account_category_waiting
    >>> template.products[0].code = 'waiting_product'
    >>> template.save()
    >>> product = template.products[0]

Create product without waiting account::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue_without_waiting
    >>> account_category.code = 'account_category'
    >>> account_category.save()
    >>> template_without_waiting = ProductTemplate()
    >>> template_without_waiting.name = 'Without Waiting Template'
    >>> template_without_waiting.default_uom = unit
    >>> template_without_waiting.type = 'service'
    >>> template_without_waiting.list_price = Decimal('40')
    >>> template_without_waiting.cost_price = Decimal('25')
    >>> template_without_waiting.account_category = account_category
    >>> template_without_waiting.products[0].code = 'without_waiting'
    >>> template_without_waiting.save()
    >>> product_without_waiting = template_without_waiting.products[0]

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='percent', ratio=Decimal('.5'))
    >>> delta = line.relativedeltas.new(days=20)
    >>> line = payment_term.lines.new(type='remainder')
    >>> delta = line.relativedeltas.new(days=40)
    >>> payment_term.save()

Create a paid invoice type "in"::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = InvoiceLine()
    >>> invoice.type = 'in'
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('40')
    >>> line.account = waiting_account
    >>> line.description = 'Test'
    >>> line2 = InvoiceLine()
    >>> line2.product = product_without_waiting
    >>> line2.quantity = 1
    >>> line2.unit_price = Decimal('60')
    >>> line2.account = revenue_without_waiting
    >>> line2.description = 'Test2'
    >>> invoice.lines.append(line)
    >>> invoice.lines.append(line2)
    >>> invoice.save()
    >>> invoice.click('post')
    >>> all(x.amount > 0 for x in invoice.move.lines if x.account == waiting_account)
    True
    >>> waiting_amount = sum(x.amount
    ...     for x in invoice.move.lines if x.account == waiting_account)
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> journal_expense, = Journal.find([('type', '=', 'expense')])
    >>> waiting_move, = Model.get('account.move').find([
    ...         ('origin', '=', 'account.invoice,' + str(invoice.id)),
    ...         ('journal', '=', journal_expense.id),
    ...         ('id', '!=', invoice.move.id)
    ...         ])
    >>> waiting_amount_paid = sum(x.amount
    ...     for x in waiting_move.lines if x.account == waiting_account)
    >>> waiting_amount != 0
    True
    >>> waiting_amount_paid != 0
    True
    >>> waiting_amount + waiting_amount_paid == 0
    True

The invoice is posted when the reconciliation is deleted::

    >>> invoice.payment_lines[0].reconciliation.delete()
    >>> invoice.reload()
    >>> waiting_move_payment_cancel, = Model.get('account.move').find([
    ...         ('origin', '=', 'account.invoice,' + str(invoice.id)),
    ...         ('journal', '=', journal_expense.id),
    ...         ('id', 'not in', [invoice.move.id, waiting_move.id])
    ...         ])
    >>> waiting_amount_payment_cancel = sum(x.amount
    ...     for x in waiting_move_payment_cancel.lines if x.account == waiting_account)
    >>> waiting_amount_payment_cancel != 0
    True
    >>> waiting_amount_paid != 0
    True
    >>> waiting_amount_payment_cancel + waiting_amount_paid == 0
    True

Create a paid invoice type "out"::

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = InvoiceLine()
    >>> invoice.lines.append(line)
    >>> line2 = InvoiceLine()
    >>> invoice.lines.append(line2)
    >>> invoice.type = 'out'
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('40')
    >>> line.account = waiting_account
    >>> line.description = 'Test'
    >>> line2.product = product_without_waiting
    >>> line2.quantity = 1
    >>> line2.unit_price = Decimal('60')
    >>> line2.account = revenue_without_waiting
    >>> line2.description = 'Test2'
    >>> invoice.save()
    >>> invoice.click('post')
    >>> all(x.amount < 0 for x in invoice.move.lines if x.account == waiting_account)
    True
    >>> waiting_amount = sum(x.amount
    ...     for x in invoice.move.lines if x.account == waiting_account)
    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')
    >>> journal_revenue, = Journal.find([('type', '=', 'revenue')])
    >>> waiting_move, = Model.get('account.move').find([
    ...         ('origin', '=', 'account.invoice,' + str(invoice.id)),
    ...         ('journal', '=', journal_revenue.id),
    ...         ('id', '!=', invoice.move.id)
    ...         ])
    >>> waiting_amount_paid = sum(x.amount
    ...     for x in waiting_move.lines if x.account == waiting_account)
    >>> waiting_amount != 0
    True
    >>> waiting_amount_paid != 0
    True
    >>> waiting_amount + waiting_amount_paid == 0
    True

The invoice is posted when the reconciliation is deleted::

    >>> invoice.payment_lines[0].reconciliation.delete()
    >>> invoice.reload()
    >>> waiting_move_payment_cancel, = Model.get('account.move').find([
    ...         ('origin', '=', 'account.invoice,' + str(invoice.id)),
    ...         ('journal', '=', journal_revenue),
    ...         ('id', 'not in', [invoice.move.id, waiting_move.id])])
    >>> waiting_amount_payment_cancel = sum(x.amount
    ...     for x in waiting_move_payment_cancel.lines if x.account == waiting_account)
    >>> waiting_amount_payment_cancel + waiting_amount_paid == 0
    True
