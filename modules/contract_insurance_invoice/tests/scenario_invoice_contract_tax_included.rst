=========================================
Contract Start Date Endorsement Scenario
=========================================

Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from decimal import Decimal
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.coog_core.test_framework import execute_test_case, \
    ...     switch_user

Install Modules::

    >>> config = activate_modules('contract_insurance_invoice')

Constants::

    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2016, 4, 10)
    >>> contract_end_date = datetime.date(2016, 6, 30)

Create or fetch Currency::

    >>> currency = get_currency(code='EUR')

Create or fetch Country::

    >>> Country = Model.get('country.country')
    >>> countries = Country.find([('code', '=', 'FR')])
    >>> if not countries:
    ...     country = Country(name='France', code='FR')
    ...     country.save()
    ... else:
    ...     country, = countries

Create Company::

    >>> _ = create_company(currency=currency)

Switch user::

    >>> execute_test_case('authorizations_test_case')
    >>> config = switch_user('financial_user')
    >>> company = get_company()

Get Models::

    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> AccountKind = Model.get('account.account.type')
    >>> Account = Model.get('account.account')
    >>> Configuration = Model.get('account.configuration')
    >>> Tax = Model.get('account.tax')

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
    >>> tax_account_kind = AccountKind()
    >>> tax_account_kind.name = 'Tax Account Kind'
    >>> tax_account_kind.company = company
    >>> tax_account_kind.save()

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
    >>> tax_account = Account()
    >>> tax_account.name = 'Main tax'
    >>> tax_account.code = 'main_tax'
    >>> tax_account.kind = 'revenue'
    >>> tax_account.company = company
    >>> tax_account.type = tax_account_kind
    >>> tax_account.save()

Define tax configuration per line::

    >>> configuration, = Configuration.find([])
    >>> configuration.tax_rounding = 'line'
    >>> configuration.save()

Create taxes::

    >>> tax1 = Tax()
    >>> tax1.name = 'Tax1'
    >>> tax1.type = 'percentage'
    >>> tax1.description = 'Tax 1'
    >>> tax1.rate = Decimal('0.0627')
    >>> tax1.company = company
    >>> tax1.invoice_account = tax_account
    >>> tax1.credit_note_account = tax_account
    >>> tax1.save()
    >>> tax2 = Tax()
    >>> tax2.name = 'Tax2'
    >>> tax2.type = 'percentage'
    >>> tax2.description = 'Tax 2'
    >>> tax2.rate = Decimal('0.07')
    >>> tax2.company = company
    >>> tax2.invoice_account = tax_account
    >>> tax2.credit_note_account = tax_account
    >>> tax2.save()
    >>> tax3 = Tax()
    >>> tax3.name = 'Tax3'
    >>> tax3.type = 'percentage'
    >>> tax3.description = 'Tax 2'
    >>> tax3.rate = Decimal('0.032')
    >>> tax3.company = company
    >>> tax3.invoice_account = tax_account
    >>> tax3.credit_note_account = tax_account
    >>> tax3.save()
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
    >>> Tax = Model.get('account.tax')

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
    >>> product_account, = Account.find([('code', '=', 'product_account')])

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
    >>> tax1, tax2, tax3 = Tax(tax1.id), Tax(tax2.id), Tax(tax3.id)
    >>> coverage = OptionDescription()
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = u'Test Coverage'
    >>> coverage.code = u'test_coverage'
    >>> coverage.start_date = product_start_date
    >>> coverage.account_for_billing = product_account
    >>> coverage.taxes_included_in_premium = True
    >>> coverage.taxes.append(tax1)
    >>> coverage.taxes.append(tax2)
    >>> coverage.taxes.append(tax3)
    >>> coverage.save()
    >>> tax1, tax2, tax3 = Tax(tax1.id), Tax(tax2.id), Tax(tax3.id)
    >>> coverage_1 = OptionDescription()
    >>> coverage_1.company = company
    >>> coverage_1.currency = currency
    >>> coverage_1.name = u'Test coverage_1'
    >>> coverage_1.code = u'test_coverage_1'
    >>> coverage_1.start_date = product_start_date
    >>> coverage_1.account_for_billing = product_account
    >>> coverage_1.taxes_included_in_premium = True
    >>> coverage_1.taxes.append(tax1)
    >>> coverage_1.taxes.append(tax2)
    >>> coverage_1.taxes.append(tax3)
    >>> coverage_1.save()
    >>> tax1, tax2, tax3 = Tax(tax1.id), Tax(tax2.id), Tax(tax3.id)
    >>> coverage_2 = OptionDescription()
    >>> coverage_2.company = company
    >>> coverage_2.currency = currency
    >>> coverage_2.name = u'Test coverage_2'
    >>> coverage_2.code = u'test_coverage_2'
    >>> coverage_2.start_date = product_start_date
    >>> coverage_2.account_for_billing = product_account
    >>> coverage_2.taxes_included_in_premium = True
    >>> coverage_2.taxes.append(tax1)
    >>> coverage_2.taxes.append(tax2)
    >>> coverage_2.taxes.append(tax3)
    >>> coverage_2.save()
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
    >>> product.taxes_included_in_premium = True
    >>> product.coverages.append(coverage)
    >>> product.coverages.append(coverage_1)
    >>> product.coverages.append(coverage_2)
    >>> product.taxes_included_in_premium = True
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
    >>> freq_monthly = BillingMode(freq_monthly.id)
    >>> payment_term = PaymentTerm(payment_term.id)
    >>> product_account, = Account.find([('code', '=', 'product_account')])
    >>> coverage = OptionDescription(coverage.id)
    >>> coverage_1 = OptionDescription(coverage_1.id)
    >>> coverage_2 = OptionDescription(coverage_2.id)
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.end_date = contract_end_date
    >>> contract.product = product
    >>> contract.status = 'quote'
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=freq_monthly, payment_term=payment_term))
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract.options[0].premiums.append(ContractPremium(start=contract_start_date,
    ...         amount=Decimal('2'), frequency='monthly',
    ...         account=product_account, rated_entity=coverage,
    ...         ))
    >>> contract.options[0].premiums.append(ContractPremium(start=contract_start_date,
    ...         amount=Decimal('2'), frequency='monthly',
    ...         account=product_account, rated_entity=coverage_1,
    ...         ))
    >>> contract.options[0].premiums.append(ContractPremium(start=contract_start_date,
    ...         amount=Decimal('2'), frequency='monthly',
    ...         account=product_account, rated_entity=coverage_2,
    ...         ))
    >>> contract.save()
    >>> Contract.first_invoice([contract.id], config.context)
    >>> contract_invoice, = ContractInvoice.find([('contract', '=', contract.id)],
    ...     order=[('start', 'ASC')], limit=1)
    >>> contract_invoice.invoice.total_amount == Decimal('6')
    True
    >>> premium = contract.options[0].premiums[0]
    >>> res = []
    >>> for premium_amount in range(100, 300):
    ...     premium.amount = Decimal(premium_amount / 100.00).quantize(
    ...         Decimal(1) / 100)
    ...     premium.save()
    ...     Contract.first_invoice([contract.id], config.context)
    ...     contract_invoice, = ContractInvoice.find(
    ...         [('contract', '=', contract.id)], order=[('start', 'ASC')], limit=1)
    ...     assert contract_invoice.invoice.total_amount == premium.amount + Decimal(4)
