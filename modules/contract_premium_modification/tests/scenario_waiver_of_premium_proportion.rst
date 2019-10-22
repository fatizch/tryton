
Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency

Install Modules::

    >>> config = activate_modules('contract_premium_modification')

Get Models::

    >>> Account = Model.get('account.account')
    >>> AccountInvoice = Model.get('account.invoice')
    >>> AccountKind = Model.get('account.account.type')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Company = Model.get('company.company')
    >>> Configuration = Model.get('account.configuration')
    >>> ConfigurationTaxRounding = Model.get('account.configuration.tax_rounding')
    >>> Contract = Model.get('contract')
    >>> ContractInvoice = Model.get('contract.invoice')
    >>> ContractPremium = Model.get('contract.premium')
    >>> Country = Model.get('country.country')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
    >>> Insurer = Model.get('insurer')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> Option = Model.get('contract.option')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> WaiverPremiumRule = Model.get('waiver_premium.rule')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> Product = Model.get('offered.product')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> User = Model.get('res.user')
    >>> Waiver = Model.get('contract.waiver_premium')
    >>> Tax = Model.get('account.tax')

Constants::

    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 1)

Create or fetch Currency::

    >>> currency = get_currency(code='EUR')

Create or fetch Country::

    >>> countries = Country.find([('code', '=', 'FR')])
    >>> if not countries:
    ...     country = Country(name='France', code='FR')
    ...     country.save()
    ... else:
    ...     country, = countries

Create Company::

    >>> _ = create_company(currency=currency)
    >>> company = get_company()

Reload the context::

    >>> config._context = User.get_preferences(True, config.context)
    >>> config._context['company'] = company.id

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
    >>> product_account_kind.statement = 'income'
    >>> product_account_kind.revenue = True
    >>> product_account_kind.save()
    >>> receivable_account_kind = AccountKind()
    >>> receivable_account_kind.name = 'Receivable Account Kind'
    >>> receivable_account_kind.company = company
    >>> receivable_account_kind.statement = 'balance'
    >>> receivable_account_kind.receivable = True
    >>> receivable_account_kind.save()
    >>> payable_account_kind = AccountKind()
    >>> payable_account_kind.name = 'Payable Account Kind'
    >>> payable_account_kind.company = company
    >>> payable_account_kind.statement = 'balance'
    >>> payable_account_kind.payable = True
    >>> payable_account_kind.save()
    >>> other_account_kind = AccountKind()
    >>> other_account_kind.name = 'Other Account Kind'
    >>> other_account_kind.company = company
    >>> other_account_kind.statement = 'balance'
    >>> other_account_kind.payable = True
    >>> other_account_kind.save()

Create Account::

    >>> product_account = Account()
    >>> product_account.name = 'Product Account'
    >>> product_account.code = 'product_account'
    >>> product_account.type = product_account_kind
    >>> product_account.company = company
    >>> product_account.save()
    >>> receivable_account = Account()
    >>> receivable_account.name = 'Account Receivable'
    >>> receivable_account.code = 'account_receivable'
    >>> receivable_account.type = receivable_account_kind
    >>> receivable_account.party_required = True
    >>> receivable_account.reconcile = True
    >>> receivable_account.company = company
    >>> receivable_account.save()
    >>> payable_account = Account()
    >>> payable_account.name = 'Account Payable'
    >>> payable_account.code = 'account_payable'
    >>> payable_account.type = payable_account_kind
    >>> payable_account.party_required = True
    >>> payable_account.company = company
    >>> payable_account.save()
    >>> tax_account_kind = AccountKind()
    >>> tax_account_kind.name = 'Tax Account Kind'
    >>> tax_account_kind.company = company
    >>> tax_account_kind.statement = 'balance'
    >>> tax_account_kind.save()
    >>> tax_account = Account()
    >>> tax_account.name = 'Main tax'
    >>> tax_account.code = 'main_tax'
    >>> tax_account.company = company
    >>> tax_account.type = tax_account_kind
    >>> tax_account.save()
    >>> payable_account_insurer = Account()
    >>> payable_account_insurer.name = 'Account Payable Insurer'
    >>> payable_account_insurer.code = 'account_payable_insurer'
    >>> payable_account_insurer.type = other_account_kind
    >>> payable_account_insurer.party_required = True
    >>> payable_account_insurer.company = company
    >>> payable_account_insurer.save()

Create billing modes::

    >>> payment_term = PaymentTerm()
    >>> payment_term.name = 'direct'
    >>> payment_term.lines.append(PaymentTermLine())
    >>> payment_term.save()
    >>> freq_quarterly = BillingMode()
    >>> freq_quarterly.name = 'Quarterly'
    >>> freq_quarterly.code = 'quarterly'
    >>> freq_quarterly.frequency = 'quarterly'
    >>> freq_quarterly.allowed_payment_terms.append(payment_term)
    >>> freq_quarterly.save()

Create billing modes::

    >>> payment_term_y = PaymentTerm()
    >>> payment_term_y.name = 'direct'
    >>> payment_term_y.lines.append(PaymentTermLine())
    >>> payment_term_y.save()
    >>> freq_yearly = BillingMode()
    >>> freq_yearly.name = 'Yearly'
    >>> freq_yearly.code = 'yearly'
    >>> freq_yearly.frequency = 'yearly'
    >>> freq_yearly.allowed_payment_terms.append(payment_term_y)
    >>> freq_yearly.sync_month = '1'
    >>> freq_yearly.sync_day = '1'
    >>> freq_yearly.save()

Define tax configuration per line::

    >>> configuration, = Configuration.find([])
    >>> configuration.tax_rounding = 'line'
    >>> configuration.save()

Create taxes::

    >>> tax1 = Tax()
    >>> tax1.name = 'Tax1'
    >>> tax1.type = 'percentage'
    >>> tax1.description = 'Tax 1'
    >>> tax1.rate = Decimal('0.1')
    >>> tax1.company = company
    >>> tax1.invoice_account = tax_account
    >>> tax1.credit_note_account = tax_account
    >>> tax1.save()
    >>> tax_waiver = Tax()
    >>> tax_waiver.name = 'Tax1'
    >>> tax_waiver.type = 'percentage'
    >>> tax_waiver.description = 'Tax 1'
    >>> tax_waiver.rate = Decimal('0.1')
    >>> tax_waiver.company = company
    >>> tax_waiver.invoice_account = payable_account_insurer
    >>> tax_waiver.credit_note_account = payable_account_insurer
    >>> tax_waiver.save()

Create Item Description::

    >>> item_description = ItemDescription()
    >>> item_description.name = 'Test Item Description'
    >>> item_description.code = 'test_item_description'
    >>> item_description.kind = 'person'
    >>> item_description.save()

Create Insurer::

    >>> insurer = Insurer()
    >>> insurer.party = Party()
    >>> insurer.party.name = 'Insurer'
    >>> insurer.party.account_receivable = receivable_account
    >>> insurer.party.account_payable = payable_account_insurer
    >>> insurer.party.save()
    >>> insurer.save()

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
    >>> product = Product()
    >>> coverage = OptionDescription()
    >>> coverage.insurer = insurer
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.item_desc = item_description
    >>> coverage.start_date = product_start_date
    >>> coverage.account_for_billing = product_account
    >>> coverage.taxes.append(tax1)
    >>> coverage.allow_subscribe_coverage_multiple_times = True
    >>> coverage.save()
    >>> waiver_rule = WaiverPremiumRule()
    >>> waiver_rule.invoice_line_period_behaviour = 'proportion'
    >>> waiver_rule.taxes.append(tax_waiver)
    >>> waiver_rule.coverage = coverage
    >>> waiver_rule.save()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.coverages.append(coverage)
    >>> product.billing_rules[-1].billing_modes.append(freq_quarterly)
    >>> product.billing_rules[-1].billing_modes.append(freq_yearly)
    >>> product.save()

Create Subscriber::

    >>> subscriber = Party()
    >>> subscriber.name = 'Doe'
    >>> subscriber.first_name = 'John'
    >>> subscriber.is_person = True
    >>> subscriber.gender = 'male'
    >>> subscriber.account_receivable = receivable_account
    >>> subscriber.account_payable = payable_account
    >>> subscriber.birth_date = datetime.date(1980, 10, 14)
    >>> subscriber.save()

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'quote'
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=freq_quarterly, payment_term=payment_term))
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> premium_0 = ContractPremium.create([{
    ...             'option': contract.covered_elements[0].options[0].id,
    ...             'start': contract_start_date,
    ...             'amount': Decimal('300'),
    ...             'frequency': 'quarterly',
    ...             'account': product_account.id,
    ...             'rated_entity': (coverage.__class__.__name__ + ','
    ...                 + str(coverage.id)),
    ...             }], config.context)
    >>> contract.save()
    >>> Contract.first_invoice([contract.id], config.context)
    >>> first_invoice = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]), key=lambda x: x.start)[0]
    >>> first_invoice.invoice.total_amount
    Decimal('330.00')
    >>> [(x.unit_price, x.coverage_start, x.coverage_end)
    ...     for x in sorted(first_invoice.invoice.lines, key=lambda x: x.unit_price)
    ...     ] == [(Decimal('300.00'),
    ...         datetime.date(2014, 4, 1), datetime.date(2014, 6, 30))]
    True
    >>> len(first_invoice.invoice.taxes) == 1
    True
    >>> first_invoice.invoice.taxes[0].amount == 30
    True
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]),
    ...     key=lambda x: x.invoice.start)
    >>> AccountInvoice.post([all_invoices[0].invoice.id], config.context)
    >>> all_invoices[0].invoice.state
    'posted'
    >>> all_invoices[0].invoice.total_amount
    Decimal('330.00')
    >>> AccountInvoice.post([all_invoices[1].invoice.id], config.context)
    >>> all_invoices[1].invoice.state
    'posted'
    >>> all_invoices[1].invoice.total_amount
    Decimal('330.00')

Test Waiver Creation Wizard::

    >>> create_wizard = Wizard(
    ...     'contract.premium_modification.create_waivers', [contract])
    >>> len(create_wizard.form.options) == 1
    True
    >>> create_wizard.form.options[0].coverage.code == 'test_coverage'
    True
    >>> create_wizard.form.start_date = datetime.date(2014, 5, 1)
    >>> create_wizard.execute('reinvoice')
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', 'in', ['posted', 'validated', 'paid'])]),
    ...     key=lambda x: x.invoice.start)
    >>> all_invoices[0].invoice.total_amount == 110
    True
    >>> all_invoices[0].invoice.state
    'posted'
    >>> all([(x.invoice.total_amount, x.invoice.state) == (0, 'paid')
    ...         for x in all_invoices[1:]])
    True

Test Set Waiver End Date Wizard::

    >>> waiver = Waiver.find([])[0]
    >>> end_date_wizard = Wizard('contract.premium_modification.set_end_date', [waiver])
    >>> end_date_wizard.form.new_end_date = datetime.date(2014, 6, 30)
    >>> end_date_wizard.execute('reinvoice')
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', 'in', ['posted', 'validated'])]),
    ...     key=lambda x: x.invoice.start)
    >>> all_invoices[0].invoice.total_amount == 110
    True
    >>> all_invoices[0].invoice.state
    'posted'
    >>> all([(x.invoice.total_amount, x.invoice.state) == (330, 'posted')
    ...         for x in all_invoices[1:]])
    True
    >>> waiver = Waiver.find([])[0]
    >>> end_date_wizard = Wizard('contract.premium_modification.set_end_date', [waiver])
    >>> end_date_wizard.form.new_end_date = None
    >>> end_date_wizard.execute('reinvoice')
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', 'in', ['posted', 'validated', 'paid'])]),
    ...     key=lambda x: x.invoice.start)
    >>> all([(x.invoice.total_amount, x.invoice.state) == (110, 'posted')
    ...         for x in all_invoices[:1]])
    True
    >>> all([(x.invoice.total_amount, x.invoice.state) == (0, 'paid')
    ...         for x in all_invoices[1:]])
    True

Create Test Contract II: Yearly contract with prorated waiver::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'quote'
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=freq_yearly, payment_term=payment_term_y))
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> premium_0 = ContractPremium.create([{
    ...             'option': contract.covered_elements[0].options[0].id,
    ...             'start': contract_start_date,
    ...             'amount': Decimal('398.18'),
    ...             'frequency': 'yearly',
    ...             'account': product_account.id,
    ...             'rated_entity': (coverage.__class__.__name__ + ','
    ...                 + str(coverage.id)),
    ...             }], config.context)
    >>> contract.save()
    >>> Contract.first_invoice([contract.id], config.context)
    >>> first_invoice = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]), key=lambda x: x.start)[0]
    >>> len(first_invoice.invoice.taxes) == 1
    True
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]),
    ...     key=lambda x: x.invoice.start)
    >>> AccountInvoice.post([all_invoices[0].invoice.id], config.context)

Test Waiver Creation Wizard::

    >>> create_wizard = Wizard('contract.premium_modification.create_waivers', [contract])
    >>> len(create_wizard.form.options) == 1
    True
    >>> create_wizard.form.options[0].coverage.code == 'test_coverage'
    True
    >>> create_wizard.form.start_date = contract_start_date + relativedelta(days=24)
    >>> create_wizard.execute('reinvoice')
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', 'in', ['posted', 'validated', 'paid'])]),
    ...     key=lambda x: x.invoice.start)
    >>> all_invoices[0].invoice.total_amount == 29.75
    True
    >>> all_invoices[0].invoice.state
    'posted'
    >>> all([(x.invoice.total_amount, x.invoice.state) == (0, 'paid')
    ...         for x in all_invoices[1:]])
    True

Test Set Waiver End Date Wizard::

    >>> waiver = Waiver.find([])[0]
    >>> end_date_wizard = Wizard('contract.premium_modification.set_end_date', [waiver])
    >>> end_date_wizard.form.new_end_date = datetime.date(2014, 12, 31)
    >>> end_date_wizard.execute('reinvoice')
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', 'in', ['posted', 'validated'])]),
    ...     key=lambda x: x.invoice.start)
    >>> all_invoices[0].invoice.total_amount == 29.75
    True
    >>> all_invoices[0].invoice.state
    'posted'
    >>> all([(x.invoice.total_amount, x.invoice.state) == (330, 'posted')
    ...         for x in all_invoices[1:]])
    True
    >>> waiver = Waiver.find([])[0]
    >>> end_date_wizard = Wizard('contract.premium_modification.set_end_date', [waiver])
    >>> end_date_wizard.form.new_end_date = None
    >>> end_date_wizard.execute('reinvoice')
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', 'in', ['posted', 'validated', 'paid'])]),
    ...     key=lambda x: x.invoice.start)
    >>> all([(x.invoice.total_amount, x.invoice.state) == (29.75, 'posted')
    ...         for x in all_invoices[:1]])
    True
    >>> all([(x.invoice.total_amount, x.invoice.state) == (0, 'paid')
    ...         for x in all_invoices[1:]])
    True
