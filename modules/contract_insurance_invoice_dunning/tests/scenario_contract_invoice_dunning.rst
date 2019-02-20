============================================
Contract Insurance Invoice Dunning Scenario
============================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.contract_insurance_invoice.tests.tools import \
    ...     add_invoice_configuration
    >>> from trytond.modules.offered.tests.tools import init_product
    >>> from trytond.modules.offered_insurance.tests.tools import \
    ...     add_insurer_to_product
    >>> from trytond.modules.party_cog.tests.tools import create_party_person
    >>> from trytond.modules.contract.tests.tools import add_quote_number_generator
    >>> from trytond.modules.country_cog.tests.tools import create_country
    >>> from trytond.modules.premium.tests.tools import add_premium_rules

Install Modules::

    >>> config = activate_modules(['contract_insurance_invoice_dunning',
    ...         'account_payment_sepa_contract', 'account_payment_clearing_contract'])

Create country::

    >>> _ = create_country()

Create currenct::

    >>> currency = get_currency(code='EUR')

Create Company::

    >>> _ = create_company(currency=currency)
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)
    >>> today = datetime.date(datetime.date.today().year, 6, 1)
    >>> config._context['client_defined_date'] = today

Create Fiscal Year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company,
    ...         today=today))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']
    >>> BillingMode = Model.get('offered.billing_mode')

Create Fee::

    >>> AccountKind = Model.get('account.account.type')
    >>> dunning_fee_kind = AccountKind()
    >>> dunning_fee_kind.name = 'Dunning Fee Account Kind'
    >>> dunning_fee_kind.company = company
    >>> dunning_fee_kind.save()
    >>> Account = Model.get('account.account')
    >>> dunning_fee_account = Account()
    >>> dunning_fee_account.name = 'Dunning Fee Account'
    >>> dunning_fee_account.code = 'dunning_fee_account'
    >>> dunning_fee_account.kind = 'revenue'
    >>> dunning_fee_account.party_required = True
    >>> dunning_fee_account.type = dunning_fee_kind
    >>> dunning_fee_account.company = company
    >>> dunning_fee_account.save()
    >>> Product = Model.get('product.product')

Create Account Product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> account_product = Product()
    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = dunning_fee_account
    >>> account_category.code = 'account_category'
    >>> account_category.save()
    >>> Template = Model.get('product.template')
    >>> template = Template()
    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> template.default_uom = unit
    >>> template.name = 'Dunning Fee Template'
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.account_category = account_category
    >>> template.products[0].code = 'dunning_fee_product'
    >>> template.save()
    >>> product_product = template.products[0]
    >>> Fee = Model.get('account.fee')
    >>> fee = Fee()
    >>> fee.name = 'Test Fee'
    >>> fee.code = 'test_fee'
    >>> fee.type = 'fixed'
    >>> fee.amount = Decimal('22')
    >>> fee.frequency = 'once_per_invoice'
    >>> fee.product = product_product
    >>> fee.save()

Create dunning procedure::

    >>> Procedure = Model.get('account.dunning.procedure')
    >>> procedure = Procedure(name='Procedure')
    >>> level = procedure.levels.new()
    >>> level.name = 'Reminder'
    >>> level.sequence = 1
    >>> level.overdue = datetime.timedelta(30)
    >>> level.apply_for = 'manual'
    >>> level = procedure.levels.new()
    >>> level.name = 'Formal Demand'
    >>> level.sequence = 2
    >>> level.overdue = datetime.timedelta(60)
    >>> level = procedure.levels.new()
    >>> level.name = 'Suspend contract'
    >>> level.sequence = 2
    >>> level.overdue = datetime.timedelta(90)
    >>> level.contract_action = 'hold'
    >>> level.dunning_fee = fee
    >>> level = procedure.levels.new()
    >>> level.name = 'Terminate contract'
    >>> level.sequence = 3
    >>> level.overdue = datetime.timedelta(100)
    >>> level.contract_action = 'terminate'
    >>> level.termination_mode = 'at_last_posted_invoice'
    >>> procedure.save()

Create Product::

    >>> product = init_product()
    >>> product = add_quote_number_generator(product)
    >>> product = add_premium_rules(product)
    >>> product = add_invoice_configuration(product, accounts)
    >>> product = add_insurer_to_product(product)
    >>> product.dunning_procedure = procedure
    >>> product.save()

Create Subscriber::

    >>> subscriber = create_party_person()
    >>> Bank = Model.get('bank')
    >>> Party = Model.get('party.party')
    >>> party_bank = Party()
    >>> party_bank.name = 'Bank'
    >>> party_bank.save()
    >>> bank = Bank()
    >>> bank.party = party_bank
    >>> bank.bic = 'NSMBFRPPXXX'
    >>> bank.save()
    >>> Number = Model.get('bank.account.number')
    >>> Account = Model.get('bank.account')
    >>> subscriber_account = Account()
    >>> subscriber_account.bank = bank
    >>> subscriber_account.owners.append(subscriber)
    >>> subscriber_account.currency = currency
    >>> subscriber_account.number = 'BE82068896274468'
    >>> subscriber_account.save()
    >>> two_months_ago = today - relativedelta(months=2)
    >>> Mandate = Model.get('account.payment.sepa.mandate')
    >>> mandate = Mandate()
    >>> mandate.company = company
    >>> mandate.party = subscriber
    >>> mandate.account_number = subscriber_account.numbers[0]
    >>> mandate.identification = 'MANDATE'
    >>> mandate.type = 'recurrent'
    >>> mandate.signature_date = two_months_ago
    >>> mandate.save()
    >>> mandate.click('request')
    >>> mandate.click('validate_mandate')

Create Payment Journal::

    >>> company_account = Account()
    >>> company_account.bank = bank
    >>> company_account.owners.append(Party(company.party.id))
    >>> company_account.currency = currency
    >>> company_account.number = 'ES8200000000000000000000'
    >>> company_account.save()
    >>> Account = Model.get('account.account')
    >>> payable = accounts['payable']
    >>> bank_clearing = Account(name='Bank Clearing', type=payable.type,
    ...     reconcile=True, deferral=True, parent=payable.parent)
    >>> bank_clearing.kind = 'other'  # Warning : on_change_parent !
    >>> bank_clearing.save()
    >>> Journal = Model.get('account.payment.journal')
    >>> journal = Journal()
    >>> journal.name = 'SEPA Journal'
    >>> journal.company = company
    >>> journal.currency = currency
    >>> journal.process_method = 'sepa'
    >>> journal.sepa_payable_flavor = 'pain.001.001.03'
    >>> journal.sepa_receivable_flavor = 'pain.008.001.02'
    >>> journal.sepa_charge_bearer = 'DEBT'
    >>> journal.sepa_bank_account_number = company_account.numbers[0]
    >>> journal.failure_billing_mode, = BillingMode.find([('code', '=',
    ...     'monthly')])
    >>> journal.always_create_clearing_move = True
    >>> journal.clearing_journal = expense
    >>> journal.clearing_account = bank_clearing
    >>> journal.save()
    >>> Configuration = Model.get('account.configuration')
    >>> configuration = Configuration(1)
    >>> configuration.direct_debit_journal = journal
    >>> configuration.save()

Create Contract::

    >>> contract_start_date = today
    >>> Contract = Model.get('contract')
    >>> ContractPremium = Model.get('contract.premium')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=product.billing_modes[0],
    ...         payment_term=product.billing_modes[0].allowed_payment_terms[0]))
    >>> contract.contract_number = '123456789'
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract.billing_information.direct_debit is False
    True

Create first invoice::

    >>> ContractInvoice = Model.get('contract.invoice')
    >>> Contract.first_invoice([contract.id], config.context)
    >>> first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
    >>> first_invoice.invoice.click('post')

Create dunnings at 30 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=30)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning, = Dunning.find([])
    >>> dunning.contract == contract
    True
    >>> dunning.procedure == procedure
    True

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'waiting'
    True
    >>> contract.dunning_status
    'Reminder'
    >>> dunning_contracts = Contract.find([('dunning_status', '=', 'Reminder')])
    >>> len(dunning_contracts)
    1

Create dunnings at 60 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=60)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning, = Dunning.find(['state', '=', 'draft'])

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'waiting'
    True

Create dunnings at 90 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=90)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning, = Dunning.find(['state', '=', 'draft'])

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'waiting'
    True
    >>> contract.status == 'hold'
    True
    >>> contract.sub_status.code == 'unpaid_premium_hold'
    True
    >>> fee_invoice, = ContractInvoice.find([('contract', '=', contract.id),
    ...         ('non_periodic', '=', True)])
    >>> fee_invoice.invoice.total_amount == Decimal('22')
    True

Create dunnings at 100 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=100)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning = Dunning.find([('state', '=', 'draft')])[0]

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'waiting'
    True
    >>> contract.end_date == first_invoice.end
    True
    >>> due_invoice = contract.due_invoices[-1]

Create payment for the first due contract invoice::

    >>> Payment = Model.get('account.payment')
    >>> MoveLine = Model.get('account.move.line')
    >>> payment_invoice = Payment()
    >>> payment_invoice.company = company
    >>> payment_invoice.journal = journal
    >>> payment_invoice.kind = 'receivable'
    >>> payment_invoice.amount = due_invoice.invoice.total_amount
    >>> payment_invoice.party = subscriber
    >>> payment_invoice.line, = MoveLine.find([('party', '=', subscriber.id),
    ...         ('account.kind', '=', 'receivable'),
    ...         ('origin', '=', 'account.invoice,%s' % due_invoice.invoice.id)])
    >>> payment_invoice.date = due_invoice.invoice.invoice_date
    >>> payment_invoice.save()
    >>> payment_invoice.click('approve')
    >>> payments = [payment_invoice]
    >>> process_payment = Wizard('account.payment.process', payments)
    >>> process_payment.execute('pre_process')
    >>> payment_invoice.click('succeed')
    >>> due_invoice.reload()
    >>> contract.reload()
    >>> contract.status == 'active'
    True
    >>> journal.last_sepa_receivable_payment_creation_date = None
    >>> journal.save()
    >>> procedure.from_payment_date = True
    >>> procedure.save()
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> payment_term = PaymentTerm()
    >>> payment_term.name = 'rest_direct'
    >>> payment_term.lines.append(PaymentTermLine())
    >>> payment_term.save()
    >>> direct_monthly = BillingMode()
    >>> direct_monthly.name = 'direct monthly'
    >>> direct_monthly.code = 'direct_monthly'
    >>> direct_monthly.frequency = 'monthly'
    >>> direct_monthly.frequency = 'monthly'
    >>> direct_monthly.allowed_payment_terms.append(payment_term)
    >>> direct_monthly.direct_debit = True
    >>> direct_monthly.allowed_direct_debit_days = '15'
    >>> direct_monthly.save()
    >>> product.billing_modes.append(direct_monthly)
    >>> product.save()
    >>> Number = Model.get('bank.account.number')
    >>> Account = Model.get('bank.account')
    >>> two_months_ago = today - relativedelta(months=2)
    >>> Product = Model.get('offered.product')
    >>> contract_start_date = datetime.date(
    ...     two_months_ago.year, two_months_ago.month, 1)
    >>> Contract = Model.get('contract')
    >>> ContractPremium = Model.get('contract.premium')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = Product(product.id)
    >>> contract.billing_informations.append(BillingInformation(
    ...         date=contract_start_date,
    ...         billing_mode=BillingMode(direct_monthly.id),
    ...         direct_debit_day=15,
    ...         direct_debit_account=Account(subscriber_account.id),
    ...         payer=subscriber.id,
    ...         payment_term=BillingMode(direct_monthly.id).allowed_payment_terms[0]))
    >>> contract.contract_number = 'test_2'
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract.billing_information.direct_debit is True
    True
    >>> bool(contract.billing_information.direct_debit_day) is True
    True
    >>> ContractInvoice = Model.get('contract.invoice')
    >>> Contract.first_invoice([contract.id], config.context)
    >>> config._context['client_defined_date'] = two_months_ago
    >>> first_invoice = ContractInvoice.find(
    ...     [('contract', '=', contract.id)],
    ...     order=[('start', 'ASC')])[0]
    >>> first_invoice.invoice.click('post')
    >>> config._context['client_defined_date'] = today
    >>> first_invoice = ContractInvoice.find(
    ...     [('contract', '=', contract.id)],
    ...     order=[('start', 'ASC')])[0]
    >>> assert all(x.maturity_date == x.payment_date
    ...     for x in first_invoice.invoice.lines_to_pay)
    >>> Contract.rebill_contracts([contract.id], contract.start_date, config.context)
    >>> first_rebilled = ContractInvoice.find([('contract', '=', contract.id),
    ...         ('invoice_state', '=', 'posted')],
    ...         order=[('start', 'ASC')])[0]
    >>> first_cancelled = ContractInvoice.find([('contract', '=', contract.id),
    ...         ('invoice_state', '=', 'cancel')],
    ...     order=[('start', 'ASC')])[0]
    >>> def key(line):
    ...     return line.maturity_date
    >>> cancelled_lines_to_pay = sorted(first_cancelled.invoice.lines_to_pay, key=key)
    >>> new_lines_to_pay = sorted(first_rebilled.invoice.lines_to_pay, key=key)
    >>> assert len(cancelled_lines_to_pay) == len(new_lines_to_pay) == 1
    >>> for cancelled, new in zip(cancelled_lines_to_pay, new_lines_to_pay):
    ...     assert new.maturity_date == cancelled.maturity_date
    ...     assert new.payment_date != cancelled.payment_date
