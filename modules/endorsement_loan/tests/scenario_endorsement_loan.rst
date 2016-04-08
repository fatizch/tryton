==========================
Loan Endorsement Scenario
==========================

Imports::

    >>> import datetime
    >>> from proteus import config, Model, Wizard
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from trytond.modules.company.tests.tools import create_company, get_company

Init Database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install Modules::

    >>> Module = Model.get('ir.module')
    >>> endorsement_loan_module = Module.find([
    ...         ('name', '=', 'endorsement_loan')])[0]
    >>> Module.install([endorsement_loan_module.id], config.context)
    >>> wizard = Wizard('ir.module.install_upgrade')
    >>> wizard.execute('upgrade')

Get Models::

    >>> Account = Model.get('account.account')
    >>> AccountInvoice = Model.get('account.invoice')
    >>> AccountKind = Model.get('account.account.type')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Company = Model.get('company.company')
    >>> Contract = Model.get('contract')
    >>> ContractInvoice = Model.get('contract.invoice')
    >>> ContractPremium = Model.get('contract.premium')
    >>> Country = Model.get('country.country')
    >>> CoveredElement = Model.get('contract.covered_element')
    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Endorsement = Model.get('endorsement')
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> EndorsementPart = Model.get('endorsement.part')
    >>> EndorsementDefinitionPartRelation = Model.get(
    ...     'endorsement.definition-endorsement.part')
    >>> EndorsementLoanField = Model.get('endorsement.loan.field')
    >>> Field = Model.get('ir.model.field')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Insurer = Model.get('insurer')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> Loan = Model.get('loan')
    >>> LoanIncrement = Model.get('loan.increment')
    >>> LoanShare = Model.get('loan.share')
    >>> LoanAveragePremiumRule = Model.get('loan.average_premium_rule')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> Option = Model.get('contract.option')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Product = Model.get('offered.product')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> User = Model.get('res.user')

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2010, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)

Create or fetch Currency::

    >>> currency, = Currency.find()
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

    >>> _ = create_company(currency=currency)
    >>> company = get_company()

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

Create Average Premium Rule::

    >>> loan_average_rule = LoanAveragePremiumRule()
    >>> loan_average_rule.name = 'Default Rule'
    >>> loan_average_rule.code = 'default_rule'
    >>> loan_average_rule.use_default_rule = True
    >>> loan_average_rule.default_fee_action = 'longest'
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
    >>> coverage.inurance_kind = 'death'
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
    >>> product.coverages.append(coverage)
    >>> product.average_loan_premium_rule = loan_average_rule
    >>> product.save()

Create Change First Payment Date::

    >>> change_first_payment_date_part = EndorsementPart()
    >>> change_first_payment_date_part.name = 'Change First Payment Date'
    >>> change_first_payment_date_part.code = 'change_first_payment_date'
    >>> change_first_payment_date_part.kind = 'loan'
    >>> change_first_payment_date_part.view = 'change_loan_data'
    >>> change_first_payment_date_part.loan_fields.append(
    ...     EndorsementLoanField(field=Field.find([
    ...                 ('model.model', '=', 'loan'),
    ...                 ('name', '=', 'first_payment_date')])[0].id))
    >>> change_first_payment_date_part.save()
    >>> change_first_payment_date = EndorsementDefinition()
    >>> change_first_payment_date.name = 'Change First Payment Date'
    >>> change_first_payment_date.code = 'change_first_payment_date'
    >>> change_first_payment_date.ordered_endorsement_parts.append(
    ...     EndorsementDefinitionPartRelation(
    ...         endorsement_part=change_first_payment_date_part))
    >>> change_first_payment_date.save()

Create Change Any Date::

    >>> change_any_date_part = EndorsementPart()
    >>> change_any_date_part.name = 'Change Any Date Date'
    >>> change_any_date_part.code = 'change_any_date'
    >>> change_any_date_part.kind = 'loan'
    >>> change_any_date_part.view = 'change_loan_any_date'
    >>> change_any_date_part.save()
    >>> change_any_date = EndorsementDefinition()
    >>> change_any_date.name = 'Change Any Date Date'
    >>> change_any_date.code = 'change_any_date'
    >>> change_any_date.ordered_endorsement_parts.append(
    ...     EndorsementDefinitionPartRelation(
    ...         endorsement_part=change_any_date_part))
    >>> change_any_date.save()

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

Create Loan::

    >>> loan_payment_date = datetime.date(2014, 5, 1)
    >>> loan_sequence = Sequence()
    >>> loan_sequence.name = 'Loan'
    >>> loan_sequence.code = 'loan'
    >>> loan_sequence.save()
    >>> loan = Loan()
    >>> loan.company = company
    >>> loan.kind = 'fixed_rate'
    >>> loan.funds_release_date = contract_start_date
    >>> loan.currency = currency
    >>> loan.first_payment_date = loan_payment_date
    >>> loan.rate = Decimal('0.045')
    >>> loan.amount = Decimal('250000')
    >>> loan.duration = 200
    >>> loan.save()
    >>> Loan.calculate_loan([loan.id], {})
    >>> loan.state == 'calculated'
    True

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'active'
    >>> contract.contract_number = '123456'
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> loan_share = option.loan_shares.new()
    >>> loan_share.loan = loan
    >>> loan_share.share = Decimal('0.95')
    >>> contract.end_date = datetime.date(2030, 12, 1)
    >>> contract.loans.append(loan)
    >>> contract.billing_informations.append(BillingInformation(
    ...         billing_mode=freq_monthly, payment_term=payment_term))
    >>> contract.save()

New Endorsement::

    >>> new_payment_date = datetime.date(2014, 4, 30)
    >>> new_end_date = datetime.date(2030, 11, 30)
    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = change_first_payment_date
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date == contract_start_date
    True
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.loan_changes[0].new_values[0].amount == loan.amount
    True
    >>> new_endorsement.form.loan_changes[0].new_values[0].first_payment_date = \
    ...     new_payment_date
    >>> new_endorsement.execute('calculate_updated_payments')
    >>> new_endorsement.execute('loan_select_contracts')
    >>> len(new_endorsement.form.selected_contracts)
    1
    >>> contract_displayer = new_endorsement.form.selected_contracts[0]
    >>> contract_displayer.contract == contract
    True
    >>> contract_displayer.to_update is True
    True
    >>> contract_displayer.new_start_date == contract.start_date
    True
    >>> contract_displayer.new_end_date == new_end_date
    True
    >>> contract_displayer.to_update = False
    >>> contract_displayer.new_end_date == None
    True
    >>> contract_displayer.to_update = True
    >>> contract_displayer.new_start_date == contract.start_date
    True
    >>> contract_displayer.new_end_date == new_end_date
    True
    >>> new_endorsement.execute('loan_endorse_selected_contracts')
    >>> new_endorsement.execute('apply_endorsement')

Test result::

    >>> new_loan_end_date = datetime.date(2030, 11, 30)
    >>> contract = Contract(contract.id)
    >>> loan = Loan(loan.id)
    >>> contract.end_date == new_end_date
    True
    >>> contract.start_date == contract_start_date
    True
    >>> loan.funds_release_date == contract_start_date
    True
    >>> loan.first_payment_date == new_payment_date
    True
    >>> loan.end_date == new_loan_end_date
    True

Test cancellation::

    >>> endorsement, = Endorsement.find([('loans', '=', loan.id)])
    >>> Endorsement.cancel([endorsement.id], config._context)
    >>> increments = LoanIncrement.find([('loan', '=', loan.id)])
    >>> len(increments) == 1
    True

 TEST CHANGE ANY DATE::


Create Loan::

    >>> funds_release_date = loan_payment_date = contract_start_date = datetime.date(
    ...     2013, 3, 22)
    >>> loan = Loan()
    >>> loan.company = company
    >>> loan.kind = 'fixed_rate'
    >>> loan.funds_release_date = contract_start_date
    >>> loan.currency = currency
    >>> loan.first_payment_date = loan_payment_date
    >>> loan.rate = Decimal('0.01')
    >>> loan.amount = Decimal('200000')
    >>> loan.duration = 360
    >>> loan.save()
    >>> Loan.calculate_loan([loan.id], {})
    >>> loan.state == 'calculated'
    True

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'active'
    >>> contract.contract_number = 'abcd'
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> loan_share = option.loan_shares.new()
    >>> loan_share.loan = loan
    >>> loan_share.share = Decimal('1.0')
    >>> contract.loans.append(loan)
    >>> contract.billing_informations.append(BillingInformation(
    ...         billing_mode=freq_monthly, payment_term=payment_term))
    >>> contract.save()

New Endorsement::

    >>> new_increment_date = datetime.date(2023, 3, 22)
    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = change_any_date
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = new_increment_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_increment = new_endorsement.form.new_increments.new()
    >>> new_increment.begin_balance = Decimal('105335.09')
    >>> new_increment.number_of_payments = 240
    >>> new_increment.rate = Decimal('0.01')
    >>> new_endorsement.execute('change_loan_any_date_next')
    >>> new_endorsement.execute('loan_select_contracts')
    >>> len(new_endorsement.form.selected_contracts)
    1
    >>> contract_displayer = new_endorsement.form.selected_contracts[0]
    >>> contract_displayer.contract == contract
    True
    >>> contract_displayer.to_update is True
    True
    >>> new_endorsement.execute('loan_endorse_selected_contracts')
    >>> new_endorsement.execute('apply_endorsement')
    >>> loan.increments[-1].early_repayment == Decimal('35066.54')
    True
