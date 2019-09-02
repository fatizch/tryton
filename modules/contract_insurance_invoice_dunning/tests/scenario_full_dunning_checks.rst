======================
Test French Procedure
======================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.coog_core.tests.tools import assert_eq
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
    >>> def today_plus(x):
    ...     return today + relativedelta(days=x)
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

Create billing mode configuration::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> BillingMode = Model.get('offered.billing_mode')
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

Create Product::

    >>> Procedure = Model.get('account.dunning.procedure')
    >>> product = init_product()
    >>> product = add_quote_number_generator(product)
    >>> product = add_premium_rules(product)
    >>> product = add_invoice_configuration(product, accounts)
    >>> product = add_insurer_to_product(product)
    >>> product.dunning_procedure, = Procedure.find(
    ...     [('code', '=', 'french_default_dunning_procedure')])
    >>> product.billing_rules[-1].billing_modes.append(direct_monthly)
    >>> product.save()

Create Subscribers::

    >>> manual_subscriber = create_party_person()
    >>> direct_debit_subscriber = create_party_person(first_name='Jane')
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
    >>> subscriber_account.owners.append(direct_debit_subscriber)
    >>> subscriber_account.currency = currency
    >>> subscriber_account.number = 'BE82068896274468'
    >>> subscriber_account.save()
    >>> Mandate = Model.get('account.payment.sepa.mandate')
    >>> mandate = Mandate()
    >>> mandate.company = company
    >>> mandate.party = direct_debit_subscriber
    >>> mandate.account_number = subscriber_account.numbers[0]
    >>> mandate.identification = 'MANDATE'
    >>> mandate.type = 'recurrent'
    >>> mandate.signature_date = today_plus(-31)
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
    >>> journal.last_sepa_receivable_payment_creation_date = None
    >>> journal.save()
    >>> Configuration = Model.get('account.configuration')
    >>> configuration = Configuration(1)
    >>> configuration.direct_debit_journal = journal
    >>> configuration.save()

Create Contracts::

    >>> Product = Model.get('offered.product')
    >>> Contract = Model.get('contract')
    >>> ContractPremium = Model.get('contract.premium')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> manual_contract = Contract()
    >>> manual_contract.company = company
    >>> manual_contract.subscriber = manual_subscriber
    >>> manual_contract.start_date = today
    >>> manual_contract.product = product
    >>> manual_contract.billing_informations[-1].billing_mode = \
    ...     product.billing_rules[-1].billing_modes[1]
    >>> manual_contract.contract_number = 'manual_contract'
    >>> manual_contract.save()
    >>> Wizard('contract.activate', models=[manual_contract]).execute('apply')
    >>> assert_eq(bool(manual_contract.billing_information.direct_debit), False)
    >>> direct_debit_contract = Model.get('contract')
    >>> direct_debit_contract = Contract()
    >>> direct_debit_contract.company = company
    >>> direct_debit_contract.subscriber = direct_debit_subscriber
    >>> direct_debit_contract.start_date = today_plus(-31)
    >>> direct_debit_contract.product = Product(product.id)
    >>> direct_debit_contract.billing_informations[-1].direct_debit_day = 15
    >>> direct_debit_contract.billing_informations[-1].direct_debit_account = Account(
    ...     subscriber_account.id)
    >>> direct_debit_contract.contract_number = 'direct_debit_contract'
    >>> direct_debit_contract.save()
    >>> Wizard('contract.activate', models=[direct_debit_contract]).execute('apply')
    >>> assert_eq(bool(direct_debit_contract.billing_information.direct_debit), True)

Create first invoices::

    >>> ContractInvoice = Model.get('contract.invoice')
    >>> Contract.first_invoice([manual_contract.id], config.context)
    >>> Contract.first_invoice([direct_debit_contract.id], config.context)
    >>> manual_first_invoice, = ContractInvoice.find(
    ...     [('contract', '=', manual_contract.id)])
    >>> manual_first_invoice.invoice.click('post')
    >>> direct_debit_first_invoice, direct_debit_second_invoice = ContractInvoice.find(
    ...     [('contract', '=', direct_debit_contract.id)], order=[('start', 'ASC')])
    >>> direct_debit_first_invoice.invoice.click('post')
    >>> direct_debit_second_invoice.invoice.click('post')
    >>> manual_line = manual_first_invoice.invoice.lines_to_pay[0]
    >>> direct_debit_line_1 = direct_debit_first_invoice.invoice.lines_to_pay[0]
    >>> direct_debit_line_2 = direct_debit_second_invoice.invoice.lines_to_pay[0]
    >>> assert_eq(manual_line.maturity_date, today)
    >>> assert_eq(manual_line.payment_date, None)
    >>> assert_eq(direct_debit_line_1.maturity_date, datetime.date(today.year,
    ...         today.month, 15))
    >>> assert_eq(direct_debit_line_1.payment_date, datetime.date(today.year,
    ...         today.month, 15))
    >>> assert_eq(direct_debit_line_2.maturity_date, datetime.date(today.year,
    ...         today.month, 15))
    >>> assert_eq(direct_debit_line_2.payment_date, datetime.date(today.year,
    ...         today.month, 15))
    >>> Dunning = Model.get('account.dunning')
    >>> Wizard('account.dunning.create').execute('create_')
    >>> assert_eq(len(Dunning.find([])), 0)

Create dunnings at 19 days::

    >>> config._context['client_defined_date'] = today_plus(19)
    >>> Wizard('account.dunning.create').execute('create_')
    >>> assert_eq(len(Dunning.find([])), 0)

Create dunnings at 20 days::

    >>> config._context['client_defined_date'] = today_plus(20)
    >>> Wizard('account.dunning.create').execute('create_')
    >>> manual_dunning, = Dunning.find([])
    >>> assert_eq(manual_dunning.line.contract.id, manual_contract.id)
    >>> assert_eq(manual_dunning.state, 'draft')
    >>> assert_eq(manual_dunning.level.name, 'Legal Dunning')
    >>> Wizard('account.dunning.process', [manual_dunning]).execute('process')
    >>> assert_eq(manual_dunning.state, 'waiting')
    >>> assert_eq(manual_dunning.last_process_date, today_plus(20))
    >>> assert_eq(manual_dunning.is_contract_main, True)
    >>> assert_eq(manual_dunning.contract.dunning_status, 'Legal Dunning')

Create dunnings at 39 days => Nothing changed::

    >>> config._context['client_defined_date'] = today_plus(39)
    >>> Wizard('account.dunning.create').execute('create_')
    >>> manual_dunning.reload()
    >>> assert_eq(len(Dunning.find([])), 1)
    >>> assert_eq(manual_dunning.state, 'waiting')
    >>> assert_eq(manual_dunning.last_process_date, today_plus(20))

Create dunnings at 40 days, manual_dunning goes draft next level::

    >>> config._context['client_defined_date'] = today_plus(40)
    >>> Wizard('account.dunning.create').execute('create_')
    >>> manual_dunning.reload()
    >>> assert_eq(len(Dunning.find([])), 1)
    >>> assert_eq(manual_dunning.state, 'draft')
    >>> assert_eq(manual_dunning.level.name, 'Formal Notice')
    >>> assert_eq(manual_dunning.last_process_date, today_plus(20))
    >>> Wizard('account.dunning.process', [manual_dunning]).execute('process')
    >>> assert_eq(manual_dunning.state, 'waiting')
    >>> assert_eq(manual_dunning.last_process_date, today_plus(40))

Create dunnings at 60 days, new dunnings for direct debit (a::

    >>> config._context['client_defined_date'] = today_plus(60)
    >>> Wizard('account.dunning.create').execute('create_')
    >>> assert_eq(len(Dunning.find([])), 3)
    >>> manual_dunning, direct_debit_dunning_1, direct_debit_dunning_2 = Dunning.find(
    ...     [])
    >>> assert_eq(manual_dunning.state, 'waiting')
    >>> assert_eq(manual_dunning.last_process_date, today_plus(40))
    >>> assert_eq(direct_debit_dunning_1.state, 'draft')
    >>> assert_eq(direct_debit_dunning_1.contract.contract_number,
    ...     'direct_debit_contract')
    >>> assert_eq(direct_debit_dunning_1.level.name, 'Formal Notice')
    >>> assert_eq(direct_debit_dunning_2.state, 'draft')
    >>> assert_eq(direct_debit_dunning_2.contract.contract_number,
    ...     'direct_debit_contract')
    >>> assert_eq(direct_debit_dunning_2.level.name, 'Formal Notice')
    >>> assert_eq(direct_debit_dunning_1.is_contract_main, True)
    >>> Wizard('account.dunning.process',
    ...     [direct_debit_dunning_1, direct_debit_dunning_2]).execute('process')
    >>> assert_eq(direct_debit_dunning_1.state, 'waiting')
    >>> assert_eq(direct_debit_dunning_1.contract.contract_number,
    ...     'direct_debit_contract')
    >>> assert_eq(direct_debit_dunning_1.last_process_date, today_plus(60))
    >>> assert_eq(direct_debit_dunning_1.level.name, 'Formal Notice')
    >>> assert_eq(direct_debit_dunning_2.state, 'draft')
    >>> assert_eq(direct_debit_contract.dunning_status, 'Formal Notice')

Create dunnings at 70 days, manual_dunning goes draft next level::

    >>> config._context['client_defined_date'] = today_plus(70)
    >>> Wizard('account.dunning.create').execute('create_')
    >>> manual_dunning.reload()
    >>> direct_debit_dunning_1.reload()
    >>> direct_debit_dunning_2.reload()
    >>> assert_eq(len(Dunning.find([])), 3)
    >>> assert_eq(manual_dunning.state, 'draft')
    >>> assert_eq(manual_dunning.level.name, 'Contract Suspension')
    >>> Wizard('account.dunning.process', [manual_dunning]).execute('process')
    >>> assert_eq(manual_dunning.state, 'waiting')
    >>> assert_eq(manual_dunning.last_process_date, today_plus(70))
    >>> assert_eq(manual_dunning.contract.dunning_status, 'Contract Suspension')
    >>> assert_eq(manual_dunning.contract.status, 'hold')
    >>> assert_eq(direct_debit_dunning_1.state, 'waiting')
    >>> assert_eq(direct_debit_dunning_1.level.name, 'Formal Notice')
    >>> assert_eq(direct_debit_dunning_2.state, 'draft')

Create dunnings at 100 days::


Create dunnings at 85 days::

    >>> config._context['client_defined_date'] = today_plus(85)
    >>> Wizard('account.dunning.create').execute('create_')
    >>> manual_dunning.reload()
    >>> direct_debit_dunning_1.reload()
    >>> direct_debit_dunning_2.reload()
    >>> assert_eq(len(Dunning.find([])), 3)
    >>> assert_eq(manual_dunning.state, 'draft')
    >>> assert_eq(manual_dunning.level.name, 'Void Contract')
    >>> assert_eq(direct_debit_dunning_1.state, 'waiting')
    >>> assert_eq(direct_debit_dunning_2.state, 'draft')
    >>> assert_eq(direct_debit_dunning_2.level.name, 'Formal Notice')
    >>> Wizard('account.dunning.process', [manual_dunning]).execute('process')
    >>> assert_eq(manual_dunning.state, 'waiting')
    >>> assert_eq(manual_dunning.last_process_date, today_plus(80))
    >>> assert_eq(manual_dunning.contract.status, 'terminated')
    >>> assert_eq(manual_dunning.contract.end_date, today_plus(80))
