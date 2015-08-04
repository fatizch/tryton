=========================================
Contract Start Date Endorsement Scenario
=========================================

Imports::

    >>> import datetime
    >>> from proteus import config, Model, Wizard
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal

Init Database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install Modules::

    >>> Module = Model.get('ir.module')
    >>> loan_invoice_module = Module.find([('name', '=', 'contract_loan_invoice')])[0]
    >>> Module.install([loan_invoice_module.id], config.context)
    >>> wizard = Wizard('ir.module.install_upgrade')
    >>> wizard.execute('upgrade')

Get Models::

    >>> Account = Model.get('account.account')
    >>> AccountInvoice = Model.get('account.invoice')
    >>> AccountProduct = Model.get('product.product')
    >>> AccountKind = Model.get('account.account.type')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Company = Model.get('company.company')
    >>> Contract = Model.get('contract')
    >>> ContractInvoice = Model.get('contract.invoice')
    >>> ContractPremium = Model.get('contract.premium')
    >>> ContractPremiumAmount = Model.get('contract.premium.amount')
    >>> Country = Model.get('country.country')
    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Fee = Model.get('account.fee')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> Loan = Model.get('loan')
    >>> LoanAveragePremiumRule = Model.get('loan.average_premium_rule')
    >>> LoanShare = Model.get('loan.share')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> Product = Model.get('offered.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> Uom = Model.get('product.uom')
    >>> User = Model.get('res.user')
    >>> Insurer = Model.get('insurer')

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)

Create or fetch Currency::

    >>> currency, = Currency.find([('code', '=', 'EUR')])
    >>> CurrencyRate(date=product_start_date, rate=Decimal('1.0'),
    ...     currency=currency).save()

Create or fetch Country::

    >>> countries = Country.find([('code', '=', 'FR')])
    >>> if not countries:
    ...     country = Country(name='France', code='FR')
    ...     country.save()
    ... else:
    ...     country, = countries

Create Company::

    >>> company_config = Wizard('company.company.config')
    >>> company_config.execute('company')
    >>> company = company_config.form
    >>> party = Party(name='World Company')
    >>> party.save()
    >>> company.party = party
    >>> company.currency = currency
    >>> company_config.execute('add')
    >>> company, = Company.find([])
    >>> user = User(1)
    >>> user.main_company = company
    >>> user.company = company
    >>> user.save()

Reload the context::

    >>> config._context = User.get_preferences(True, config.context)
    >>> config._context['company'] = company.id

Create Fiscal Year::

    >>> fiscalyear = FiscalYear(name=str(today.year))
    >>> fiscalyear.start_date = today + relativedelta(month=1, day=1)
    >>> fiscalyear.end_date = today + relativedelta(month=12, day=31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name=str(today.year), code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> invoice_seq = SequenceStrict(name=str(today.year),
    ...     code='account.invoice', company=company)
    >>> invoice_seq.save()
    >>> fiscalyear.out_invoice_sequence = invoice_seq
    >>> fiscalyear.in_invoice_sequence = invoice_seq
    >>> fiscalyear.out_credit_note_sequence = invoice_seq
    >>> fiscalyear.in_credit_note_sequence = invoice_seq
    >>> fiscalyear.save()
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

Create Fee::

    >>> product_template = ProductTemplate()
    >>> product_template.name = 'Fee'
    >>> product_template.type = 'service'
    >>> product_template.default_uom = Uom(1)
    >>> product_template.list_price = Decimal(1)
    >>> product_template.cost_price = Decimal(0)
    >>> product_template.save()
    >>> product = AccountProduct()
    >>> product.template = product_template
    >>> product.type = 'service'
    >>> product.default_uom = product_template.default_uom
    >>> product.save()
    >>> fee = Fee()
    >>> fee.name = 'Test Fee'
    >>> fee.code = 'test_fee'
    >>> fee.type = 'fixed'
    >>> fee.amount = Decimal('20')
    >>> fee.frequency = 'once_per_contract'
    >>> fee.product = product
    >>> fee.save()

Create Loan Average Premium Rule::

    >>> loan_average_rule = LoanAveragePremiumRule()
    >>> loan_average_rule.name = 'Test Average Rule'
    >>> loan_average_rule.code = 'test_average_rule'
    >>> loan_average_rule.use_default_rule = True
    >>> fee_rule = loan_average_rule.fee_rules.new()
    >>> fee_rule.fee = fee
    >>> fee_rule.action = 'longest'
    >>> loan_average_rule.save()

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
    >>> insurer.party.account_payable = payable_account
    >>> insurer.party.save()
    >>> insurer.save()

Create Coverage::

    >>> coverage = OptionDescription()
    >>> coverage.company = company
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.family = 'loan'
    >>> coverage.start_date = product_start_date
    >>> coverage.account_for_billing = product_account
    >>> coverage.item_desc = item_description
    >>> coverage.insurer = insurer
    >>> coverage.save()

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
    >>> product.company = company
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.billing_modes.append(freq_monthly)
    >>> product.billing_modes.append(freq_yearly)
    >>> product.average_loan_premium_rule = loan_average_rule
    >>> product.coverages.append(coverage)
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

Create Loans::

    >>> loan_payment_date = datetime.date(2014, 5, 1)
    >>> loan_sequence = Sequence()
    >>> loan_sequence.name = 'Loan'
    >>> loan_sequence.code = 'loan'
    >>> loan_sequence.save()
    >>> loan_1 = Loan()
    >>> loan_1.company = company
    >>> loan_1.kind = 'fixed_rate'
    >>> loan_1.funds_release_date = contract_start_date
    >>> loan_1.currency = currency
    >>> loan_1.first_payment_date = loan_payment_date
    >>> loan_1.rate = Decimal('0.045')
    >>> loan_1.amount = Decimal('250000')
    >>> loan_1.number_of_payments = 200
    >>> loan_1.save()
    >>> loan_2 = Loan()
    >>> loan_2.company = company
    >>> loan_2.kind = 'fixed_rate'
    >>> loan_2.funds_release_date = contract_start_date
    >>> loan_2.currency = currency
    >>> loan_2.first_payment_date = loan_payment_date
    >>> loan_2.rate = Decimal('0.03')
    >>> loan_2.amount = Decimal('100000')
    >>> loan_2.number_of_payments = 220
    >>> loan_2.save()
    >>> Loan.calculate_loan([loan_1.id, loan_2.id], {})

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> loan_share_1 = option.loan_shares.new()
    >>> loan_share_1.loan = loan_1
    >>> loan_share_1.share = Decimal('0.7')
    >>> loan_share_2 = option.loan_shares.new()
    >>> loan_share_2.loan = loan_2
    >>> loan_share_2.share = Decimal('0.9')
    >>> contract_premium = contract.premiums.new()
    >>> contract_premium.start = contract_start_date
    >>> contract_premium.amount = Decimal('2')
    >>> contract_premium.frequency = 'monthly'
    >>> contract_premium.account = product_account
    >>> contract_premium.rated_entity = fee
    >>> option_premium_1 = option.premiums.new()
    >>> option_premium_1.start = contract_start_date
    >>> option_premium_1.amount = Decimal('20')
    >>> option_premium_1.frequency = 'monthly'
    >>> option_premium_1.account = product_account
    >>> option_premium_1.rated_entity = coverage
    >>> option_premium_1.loan = loan_1
    >>> option_premium_2 = option.premiums.new()
    >>> option_premium_2.start = contract_start_date
    >>> option_premium_2.amount = Decimal('200')
    >>> option_premium_2.frequency = 'monthly'
    >>> option_premium_2.account = product_account
    >>> option_premium_2.rated_entity = coverage
    >>> option_premium_2.loan = loan_2
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=freq_yearly, payment_term=payment_term))
    >>> contract.contract_number = '123456789'
    >>> contract.status = 'active'
    >>> contract.save()

Test loan_share end_date calculation::

    >>> new_share_date = datetime.date(2014, 9, 12)
    >>> option = contract.covered_elements[0].options[0]
    >>> loan_share_3 = LoanShare()
    >>> loan_share_3.start_date = new_share_date
    >>> loan_share_3.loan = loan_1
    >>> loan_share_3.share = Decimal('0.5')
    >>> loan_share_3.option = option
    >>> loan_share_3.save()
    >>> loan_share_1 = LoanShare(
    ...     contract.covered_elements[0].options[0].loan_shares[0].id)
    >>> loan_share_1.end_date == datetime.date(2014, 9, 11)
    True
    >>> loan_share_3.end_date == loan_1.end_date
    True
    >>> LoanShare.delete([loan_share_3])

Create Premium Amounts::

    >>> contract = Contract(contract.id)
    >>> option = contract.covered_elements[0].options[0]
    >>> premium_amounts = [
    ...     ContractPremiumAmount(contract=contract, premium=contract.premiums[0],
    ...         start=contract_start_date, end=contract_start_date,
    ...         amount=Decimal(100)),
    ...     ContractPremiumAmount(contract=contract, premium=option.premiums[0],
    ...         start=contract_start_date, end=contract_start_date,
    ...         amount=Decimal(20)),
    ...     ContractPremiumAmount(contract=contract, premium=option.premiums[0],
    ...         start=contract_start_date, end=contract_start_date,
    ...         amount=Decimal(100)),
    ...     ContractPremiumAmount(contract=contract, premium=option.premiums[1],
    ...         start=contract_start_date, end=contract_start_date,
    ...         amount=Decimal(200)),
    ...     ]
    >>> void_val = [x.save() for x in premium_amounts]

Test Average Premium Rate Wizard, fee => longest::

    >>> loan_average = Wizard('loan.average_premium_rate.display', models=[contract])
    >>> loans = loan_average.form.loan_displayers
    >>> abs(loans[0].average_premium_rate - Decimal('0.00428571')) <= Decimal('1e-8')
    True
    >>> abs(loans[1].average_premium_rate - Decimal('0.01851851')) <= Decimal('1e-8')
    True
    >>> abs(loans[0].current_loan_shares[0].average_premium_rate -
    ...     Decimal('0.00428571')) <= Decimal('1e-8')
    True
    >>> loans[0].base_premium_amount == 120
    True
    >>> loans[1].base_premium_amount == 300
    True
    >>> loan_average.execute('end')

Test Average Premium Rate Wizard, fee => biggest::

    >>> loan_average_rule.fee_rules[0].action = 'biggest'
    >>> loan_average_rule.save()
    >>> loan_average = Wizard('loan.average_premium_rate.display', models=[contract])
    >>> loans = loan_average.form.loan_displayers
    >>> abs(loans[0].average_premium_rate - Decimal('0.00785714')) <= Decimal('1e-8')
    True
    >>> abs(loans[1].average_premium_rate - Decimal('0.01234567')) <= Decimal('1e-8')
    True
    >>> loans[0].base_premium_amount == 220
    True
    >>> loans[1].base_premium_amount == 200
    True
    >>> loan_average.execute('end')

Test Average Premium Rate Wizard, fee => prorata::

    >>> loan_average_rule.fee_rules[0].action = 'prorata'
    >>> loan_average_rule.save()
    >>> loan_average = Wizard('loan.average_premium_rate.display', models=[contract])
    >>> loans = loan_average.form.loan_displayers
    >>> abs(loans[0].average_premium_rate - Decimal('0.00664420')) <= Decimal('1e-8')
    True
    >>> abs(loans[1].average_premium_rate - Decimal('0.01444211')) <= Decimal('1e-8')
    True
    >>> abs(loans[0].base_premium_amount - Decimal('186.037735')) <= Decimal('1e-6')
    True
    >>> abs(loans[1].base_premium_amount - Decimal('233.962264')) <= Decimal('1e-6')
    True
    >>> loan_average.execute('end')
