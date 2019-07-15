=================================================
Full Contract Revision Loan Endorsement Scenario
=================================================
==========================
Loan Endorsement Scenario
==========================

Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from decimal import Decimal
    >>> from dateutil.relativedelta import relativedelta
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency

Install Modules::

    >>> config = activate_modules('endorsement_full_contract_revision_loan')

Get Models::

    >>> Account = Model.get('account.account')
    >>> AccountInvoice = Model.get('account.invoice')
    >>> AccountKind = Model.get('account.account.type')
    >>> Action = Model.get('ir.action')
    >>> Address = Model.get('party.address')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Company = Model.get('company.company')
    >>> Contract = Model.get('contract')
    >>> ContractInvoice = Model.get('contract.invoice')
    >>> ContractPremium = Model.get('contract.premium')
    >>> Country = Model.get('country.country')
    >>> CoveredElement = Model.get('contract.covered_element')
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> EndorsementPart = Model.get('endorsement.part')
    >>> EndorsementDefinitionPartRelation = Model.get(
    ...     'endorsement.definition-endorsement.part')
    >>> EndorsementLoanField = Model.get('endorsement.loan.field')
    >>> Field = Model.get('ir.model.field')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> IrModel = Model.get('ir.model')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> Loan = Model.get('loan')
    >>> LoanShare = Model.get('loan.share')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> Process = Model.get('process')
    >>> ProcessStep = Model.get('process.step')
    >>> Option = Model.get('contract.option')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Product = Model.get('offered.product')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> User = Model.get('res.user')
    >>> Insurer = Model.get('insurer')
    >>> ZipCode = Model.get('country.zip')
    >>> View = Model.get('ir.ui.view')

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)

Create or fetch Currency::

    >>> currency = get_currency(code='EUR')

Create or fetch Country::

    >>> countries = Country.find([('code', '=', 'FR')])
    >>> if not countries:
    ...     country = Country(name='France', code='FR')
    ...     country.save()
    ... else:
    ...     country, = countries
    >>> _ = create_company(currency=currency)
    >>> company = get_company()

Reload the context::

    >>> config._context = User.get_preferences(True, config.context)
    >>> config._context['company'] = company.id

Create Fiscal Year::

    >>> base_year = 2014
    >>> while base_year <= datetime.date.today().year + 1:
    ...     fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(
    ...         company, today=datetime.date(base_year, 1, 1)))
    ...     fiscalyear.click('create_period')
    ...     base_year += 1

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
    >>> receivable_account.party_required = True
    >>> receivable_account.reconcile = True
    >>> receivable_account.type = receivable_account_kind
    >>> receivable_account.company = company
    >>> receivable_account.save()
    >>> payable_account = Account()
    >>> payable_account.name = 'Account Payable'
    >>> payable_account.code = 'account_payable'
    >>> payable_account.kind = 'payable'
    >>> payable_account.party_required = True
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
    >>> coverage.currency = currency
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
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.billing_rules[-1].billing_modes.append(freq_monthly)
    >>> product.billing_rules[-1].billing_modes.append(freq_yearly)
    >>> product.coverages.append(coverage)
    >>> product.save()

Create Full Revision Process::

    >>> contract_model, = IrModel.find([
    ...         ('model', '=', 'contract')])
    >>> step = ProcessStep()
    >>> step.fancy_name = 'Full Contract Revision'
    >>> step.technical_name = 'full_contract_revision'
    >>> step.main_model = contract_model
    >>> step_action = step.code_after.new()
    >>> step_action.technical_kind = 'step_after'
    >>> step_action.method_name = 'activate_contract'
    >>> step_action = step.code_after.new()
    >>> step_action.technical_kind = 'step_after'
    >>> step_action.method_name = 'apply_in_progress_endorsement'
    >>> step.save()
    >>> process = Process()
    >>> process.fancy_name = 'Full Contract Revision'
    >>> process.technical_name = 'full_contract_revision'
    >>> process.on_model = contract_model
    >>> process.kind = 'full_contract_revision'
    >>> process.start_date = product_start_date
    >>> process.steps_to_display.append(step)
    >>> process.save()

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
    >>> receivable_account2 = Account()
    >>> receivable_account2.name = 'Account Receivable 2'
    >>> receivable_account2.code = 'account_receivable 2'
    >>> receivable_account2.kind = 'receivable'
    >>> receivable_account2.party_required = True
    >>> receivable_account2.reconcile = True
    >>> receivable_account2.type = receivable_account_kind
    >>> receivable_account2.company = company
    >>> receivable_account2.save()
    >>> payable_account2 = Account()
    >>> payable_account2.name = 'Account Payable 2'
    >>> payable_account2.code = 'account_payable 2'
    >>> payable_account2.kind = 'payable'
    >>> payable_account2.party_required = True
    >>> payable_account2.type = payable_account_kind
    >>> payable_account2.company = company
    >>> payable_account2.save()
    >>> bank_party = Party()
    >>> bank_party.name = 'Bank of Mordor'
    >>> bank_party.account_receivable = receivable_account2
    >>> bank_party.account_payable = payable_account2
    >>> lender = bank_party.lender_role.new()
    >>> bank_party.save()
    >>> zip_ = ZipCode(zip="1", city="Mount Doom", country=country)
    >>> zip_.save()
    >>> bank_address = Address(party=bank_party.id, zip="1", country=country,
    ...     city="Mount Doom")
    >>> bank_address.save()

Create Loan::

    >>> loan_payment_date = datetime.date(2014, 5, 1)
    >>> loan_sequence = Sequence()
    >>> loan_sequence.name = 'Loan'
    >>> loan_sequence.code = 'loan'
    >>> loan_sequence.save()
    >>> loan = Loan()
    >>> loan.lender_address = bank_address
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
    >>> ordered_loan = contract.ordered_loans.new()
    >>> ordered_loan.loan = loan
    >>> ordered_loan.number = 1
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> loan_share = option.loan_shares.new()
    >>> loan_share.loan = loan
    >>> loan_share.share = Decimal('0.95')
    >>> contract.end_date = datetime.date(2030, 12, 1)
    >>> contract.billing_informations.append(BillingInformation(
    ...         billing_mode=freq_monthly, payment_term=payment_term))
    >>> contract.save()
    >>> Contract.first_invoice([contract.id], config.context)
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id)]),
    ...     key=lambda x: (x.start or datetime.date.min, x.create_date))
    >>> all_invoices[0].invoice.click('post')

Start Endorsement::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = EndorsementDefinition.find([
    ...         ('code', '=', 'full_contract_revision')])[0]
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = contract.start_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.execute('full_contract_revision_next')

Modify Contract::

    >>> loan = Loan(loan.id)
    >>> loan.amount == Decimal('250000')
    True
    >>> Loan.draft([loan.id], {})
    >>> loan = Loan(loan.id)
    >>> loan.amount = Decimal('1000000')
    >>> loan.save()
    >>> Loan.calculate_loan([loan.id], {})

Revert Current process::

    >>> Contract.revert_current_endorsement([contract.id], config._context)
    'close'
    >>> loan = Loan(loan.id)
    >>> loan.amount == Decimal('250000')
    True

Start Again::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = EndorsementDefinition.find([
    ...         ('code', '=', 'full_contract_revision')])[0]
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = contract.start_date + relativedelta(
    ...     months=1)
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.execute('full_contract_revision_next')

Modify Contract::

    >>> loan = Loan(loan.id)
    >>> loan.amount == Decimal('250000')
    True
    >>> Loan.draft([loan.id], {})
    >>> loan = Loan(loan.id)
    >>> loan.amount = Decimal('1000000')
    >>> loan.save()
    >>> Loan.calculate_loan([loan.id], {})

This time, complete::

    >>> end_view, = View.find([
    ...         ('name', '=', 'process_view_contract_terminated_en')])
    >>> end_process, = Action.find([
    ...         ('xml_id', '=', 'process_cog.act_end_process')])
    >>> Contract._proxy._button_next_1([contract.id], config._context) == [
    ...     end_process.id, 'toggle_view:%s' % end_view.id]
    True
    >>> contract = Contract(contract.id)
    >>> loan = Loan(loan.id)
    >>> loan.amount == Decimal('1000000')
    True
