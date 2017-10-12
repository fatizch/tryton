=========================================
Contract Start Date Endorsement Scenario
=========================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.error import UserWarning
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import get_accounts, create_chart
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.coog_core.test_framework import execute_test_case, \
    ...     switch_user

Install Modules::

    >>> config = activate_modules('contract_insurance_invoice')

Constants::

    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)

Create or fetch Currency::

    >>> currency = get_currency(code='EUR')

Create or fetch Country::

    >>> Country = Model.get('country.country')
    >>> countries = Country.find([('code', '=', 'FR')])
    >>> if not countries:
    ...     country = Country(name='France', code='FR')
    ...     country.save()

Create Company::

    >>> _ = create_company(currency=currency)

Switch user::

    >>> execute_test_case('authorizations_test_case')
    >>> config = switch_user('financial_user')
    >>> company = get_company()
    >>> Account = Model.get('account.account')
    >>> AccountInvoice = Model.get('account.invoice')
    >>> AccountKind = Model.get('account.account.type')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')

Create Fiscal Year::

    >>> fiscalyear = FiscalYear(name='2014')
    >>> fiscalyear.start_date = datetime.date(datetime.date.today().year, 1, 1)
    >>> fiscalyear.end_date = datetime.date(datetime.date.today().year, 12, 31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name='2014', code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> seq = SequenceStrict(name='2014',
    ...     code='account.invoice', company=company)
    >>> seq.save()
    >>> bool(fiscalyear.invoice_sequences.pop())
    True
    >>> fiscalyear.save()
    >>> invoice_sequence = InvoiceSequence()
    >>> invoice_sequence.out_invoice_sequence = seq
    >>> invoice_sequence.in_invoice_sequence = seq
    >>> invoice_sequence.out_credit_note_sequence = seq
    >>> invoice_sequence.in_credit_note_sequence = seq
    >>> invoice_sequence.fiscalyear = fiscalyear
    >>> invoice_sequence.company = company
    >>> invoice_sequence.save()
    >>> fiscalyear.reload()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

Create Account Kind::

    >>> product_account_kind = AccountKind()
    >>> product_account_kind.name = 'Product Account Kind'
    >>> product_account_kind.company = company
    >>> product_account_kind.save()
    >>> receivable_account_kind = AccountKind()
    >>> receivable_account_kind.name = 'Receivable Account Kind'
    >>> receivable_account_kind.company = company
    >>> receivable_account_kind.save()
    >>> payable_account_kind = AccountKind()
    >>> payable_account_kind.name = 'Payable Account Kind'
    >>> payable_account_kind.company = company
    >>> payable_account_kind.save()

Create Account::

    >>> product_account = Account()
    >>> product_account.name = 'Product Account'
    >>> product_account.code = 'product_account'
    >>> product_account.kind = 'revenue'
    >>> product_account.type = product_account_kind
    >>> product_account.company = company
    >>> product_account.save()
    >>> receivable_account = Account()
    >>> receivable_account.name = 'Account Receivable'
    >>> receivable_account.code = 'account_receivable'
    >>> receivable_account.kind = 'receivable'
    >>> receivable_account.reconcile = True
    >>> receivable_account.type = receivable_account_kind
    >>> receivable_account.company = company
    >>> receivable_account.save()
    >>> payable_account = Account()
    >>> payable_account.name = 'Account Payable'
    >>> payable_account.code = 'account_payable'
    >>> payable_account.kind = 'payable'
    >>> payable_account.type = payable_account_kind
    >>> payable_account.company = company
    >>> payable_account.save()
    >>> _ = create_chart(company)
    >>> config = switch_user('product_user')
    >>> company = get_company()
    >>> currency = get_currency(code='EUR')
    >>> Account = Model.get('account.account')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Product = Model.get('offered.product')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> Sequence = Model.get('ir.sequence')
    >>> OptionDescription = Model.get('offered.option.description')

Create billing modes::

    >>> payment_term = PaymentTerm()
    >>> payment_term.name = 'direct'
    >>> payment_term.lines.append(PaymentTermLine())
    >>> payment_term.save()
    >>> freq_monthly = BillingMode()
    >>> freq_monthly.name = 'Monthly'
    >>> freq_monthly.code = 'monthly'
    >>> freq_monthly.frequency = 'monthly'
    >>> freq_monthly.allowed_payment_terms.append(payment_term)
    >>> freq_monthly.save()
    >>> freq_yearly = BillingMode()
    >>> freq_yearly.name = 'Yearly'
    >>> freq_yearly.code = 'yearly'
    >>> freq_yearly.frequency = 'yearly'
    >>> freq_yearly.allowed_payment_terms.append(PaymentTerm.find([])[0])
    >>> freq_yearly.save()

Create Product::

    >>> sequence_code = SequenceType()
    >>> sequence_code.name = 'Product sequence'
    >>> sequence_code.code = 'contract'
    >>> sequence_code.company = company
    >>> sequence_code.save()
    >>> contract_sequence = Sequence()
    >>> contract_sequence.name = 'Contract Sequence'
    >>> contract_sequence.code = sequence_code.code
    >>> contract_sequence.company = company
    >>> contract_sequence.save()
    >>> quote_sequence_code = SequenceType()
    >>> quote_sequence_code.name = 'Product sequence'
    >>> quote_sequence_code.code = 'quote'
    >>> quote_sequence_code.company = company
    >>> quote_sequence_code.save()
    >>> quote_sequence = Sequence()
    >>> quote_sequence.name = 'Quote Sequence'
    >>> quote_sequence.code = quote_sequence_code.code
    >>> quote_sequence.company = company
    >>> quote_sequence.save()
    >>> coverage = OptionDescription()
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = u'Test Coverage'
    >>> coverage.code = u'test_coverage'
    >>> coverage.start_date = product_start_date
    >>> product_account, = Account.find([('code', '=', 'product_account')])
    >>> coverage.account_for_billing = product_account
    >>> coverage.save()
    >>> accounts = get_accounts(company)

Create Contract Fee::

    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> AccountProduct = Model.get('product.product')
    >>> Template = Model.get('product.template')
    >>> template = Template()
    >>> template.name = 'contract Fee Template'
    >>> template.default_uom = unit
    >>> template.account_expense = accounts['expense']
    >>> template.account_revenue = accounts['revenue']
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.save()
    >>> fee_product = AccountProduct()
    >>> fee_product.name = 'contract Fee Product'
    >>> fee_product.template = template
    >>> fee_product.save()
    >>> Fee = Model.get('account.fee')
    >>> contract_fee = Fee()
    >>> contract_fee.name = 'contract Fee'
    >>> contract_fee.code = 'contract_fee'
    >>> contract_fee.frequency = 'at_contract_signature'
    >>> contract_fee.type = 'fixed'
    >>> contract_fee.amount = Decimal('800.0')
    >>> contract_fee.product = fee_product
    >>> contract_fee.save()
    >>> product = Product()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.billing_modes.append(freq_monthly)
    >>> product.billing_modes.append(freq_yearly)
    >>> product.coverages.append(coverage)
    >>> product.fees.append(contract_fee)
    >>> product.save()
    >>> config = switch_user('contract_user')
    >>> Account = Model.get('account.account')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Contract = Model.get('contract')
    >>> ContractInvoice = Model.get('contract.invoice')
    >>> ContractPremium = Model.get('contract.premium')
    >>> Option = Model.get('contract.option')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> product = Model.get('offered.product')(product.id)
    >>> company = get_company()

Create Subscriber::

    >>> subscriber = Party()
    >>> subscriber.name = 'Doe'
    >>> subscriber.first_name = 'John'
    >>> subscriber.is_person = True
    >>> subscriber.gender = 'male'
    >>> subscriber.account_receivable = Account(receivable_account.id)
    >>> subscriber.account_payable = Account(payable_account.id)
    >>> subscriber.birth_date = datetime.date(1980, 10, 14)
    >>> subscriber.save()

Create Test Contract::

    >>> freq_yearly = BillingMode(freq_yearly.id)
    >>> payment_term = PaymentTerm(payment_term.id)
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'quote'
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=freq_yearly, payment_term=payment_term))
    >>> contract.save()
    >>> product_account, = Account.find([('code', '=', 'product_account')])
    >>> coverage = OptionDescription(coverage.id)
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract.options[0].premiums.append(ContractPremium(start=contract_start_date,
    ...         amount=Decimal('100'), frequency='once_per_contract',
    ...         account=product_account, rated_entity=coverage))
    >>> contract.premiums.append(ContractPremium(start=contract_start_date,
    ...         amount=Decimal('15'), frequency='monthly', account=product_account,
    ...         rated_entity=product))
    >>> contract.premiums.append(ContractPremium(
    ...         start=contract_start_date + datetime.timedelta(days=40),
    ...         amount=Decimal('20'), frequency='yearly', account=product_account,
    ...         rated_entity=coverage))
    >>> contract.save()
    >>> all_invoices = ContractInvoice.find([('contract', '=', contract.id)])
    >>> len(all_invoices)
    1
    >>> all_invoices[0].invoice.state
    u'posted'

Test invoicing::

    >>> Contract.first_invoice([contract.id], config.context)
    >>> all_invoices = ContractInvoice.find([('contract', '=', contract.id)])
    >>> len(all_invoices) == 2 + relativedelta(datetime.date.today(),
    ...     contract.start_date).years
    True
    >>> first_invoice = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]), key=lambda x: x.start)[0]
    >>> first_invoice.invoice.total_amount
    Decimal('297.81')
    >>> [(x.rec_name, x.unit_price, x.coverage_start, x.coverage_end)
    ...     for x in sorted(first_invoice.invoice.lines, key=lambda x: x.unit_price)
    ...     ] == [
    ...     (u'1', Decimal('17.81'),
    ...         datetime.date(2014, 5, 20), datetime.date(2015, 4, 9)),
    ...     (u'Test Coverage', Decimal('100.00'),
    ...         datetime.date(2014, 4, 10), datetime.date(2015, 4, 9)),
    ...     (u'1', Decimal('180.00'),
    ...         datetime.date(2014, 4, 10), datetime.date(2015, 4, 9)),
    ...     ]
    True
    >>> Contract.first_invoice([contract.id], config.context)
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]),
    ...     key=lambda x: x.invoice.start)
    >>> def test_posting(ids_to_test):
    ...     try:
    ...         AccountInvoice.post(ids_to_test, config.context)
    ...         raise Exception('Failed example, expected to raise UserWarning')
    ...     except UserWarning:
    ...         pass
    >>> test_posting([all_invoices[-1].invoice.id])
    >>> AccountInvoice.post([all_invoices[0].invoice.id], config.context)
    >>> all_invoices[0].invoice.state
    u'posted'
    >>> Contract.first_invoice([contract.id], config.context)
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id)]),
    ...     key=lambda x: (x.start or datetime.date.min, x.create_date))
    >>> len(all_invoices) == 3 + relativedelta(datetime.date.today(),
    ...     contract.start_date).years
    True
    >>> all_invoices[0].invoice.total_amount
    Decimal('800.00')
    >>> all_invoices[0].invoice.state
    u'posted'
    >>> all_invoices[1].invoice.state
    u'cancel'
    >>> all_invoices[2].invoice.state
    u'validated'

Test option declined::

    >>> contract = Contract(contract.id)
    >>> option_id = contract.options[0].id
    >>> Option.delete([Option(option_id)])
    >>> Option(option_id).status
    u'declined'
    >>> contract = Contract(contract.id)
    >>> len(contract.options)
    0
    >>> len(contract.declined_options)
    1
