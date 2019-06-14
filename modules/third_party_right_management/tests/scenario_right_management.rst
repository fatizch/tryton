======================================
Third Party Right Management Scenario
======================================

Imports::

    >>> import datetime as dt
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> from trytond.modules.party_cog.tests.tools import create_party_person, \
    ...     create_party_company
    >>> from trytond.modules.country_cog.tests.tools import create_country
    >>> from trytond.modules.coog_core.test_framework import execute_test_case, \
    ...     switch_user

Install Modules::

    >>> config = activate_modules([
    ...      'third_party_right_management', 'contract_insurance_suspension'],
    ...     cache_file_name='third_party_right_management_scen_3')

Create country::

    >>> _ = create_country()

Create currency::

    >>> currency = get_currency(code='EUR')

Create Company::

    >>> _ = create_company(currency=currency)

Switch user::

    >>> execute_test_case('authorizations_test_case')
    >>> config = switch_user('financial_user')
    >>> company = get_company()

Create Fiscal Year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create Account Kind::

    >>> AccountKind = Model.get('account.account.type')
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

    >>> Account = Model.get('account.account')
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

Create Insurer::

    >>> config = switch_user('product_user')
    >>> company = get_company()
    >>> currency = get_currency(code='EUR')
    >>> Insurer = Model.get('insurer')
    >>> Party = Model.get('party.party')
    >>> Account = Model.get('account.account')
    >>> insurer = Insurer()
    >>> insurer.party = Party()
    >>> insurer.party.name = 'Insurer'
    >>> insurer.party.account_receivable = Account(receivable_account.id)
    >>> insurer.party.account_payable = Account(payable_account.id)
    >>> insurer.party.save()
    >>> insurer.save()

Create Item Description::

    >>> ItemDescription = Model.get('offered.item.description')
    >>> item_description = ItemDescription()
    >>> item_description.name = 'Test Item Description'
    >>> item_description.code = 'test_item_description'
    >>> item_description.kind = 'person'
    >>> item_description.save()

Create Product::

    >>> SequenceType = Model.get('ir.sequence.type')
    >>> Sequence = Model.get('ir.sequence')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Product = Model.get('offered.product')
    >>> SubStatus = Model.get('contract.sub_status')
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
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.start_date = dt.date(2014, 1, 1)
    >>> coverage.item_desc = item_description
    >>> coverage.insurer = insurer
    >>> coverage.subscription_behaviour = 'optional'
    >>> coverage.account_for_billing = Model.get('account.account')(product_account.id)
    >>> coverage.save()
    >>> product = Product()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = dt.date(2014, 1, 1)
    >>> product.coverages.append(coverage)
    >>> product.save()

Create Subscriber::

    >>> config = switch_user('contract_user')
    >>> subscriber = create_party_person()

Create a manager::

    >>> config = switch_user('admin')
    >>> party_manager = create_party_company()

Create Protocol::

    >>> Rule = Model.get('rule_engine')
    >>> RuleContext = Model.get('rule_engine.context')
    >>> ThirdPartyManager = Model.get('third_party_manager')
    >>> Protocol = Model.get('third_party_manager.protocol')
    >>> EventType = Model.get('event.type')
    >>> manager = ThirdPartyManager()
    >>> manager.party = party_manager
    >>> manager.save()
    >>> context = RuleContext(1)
    >>> rule = Rule()
    >>> rule.short_name = 'test'
    >>> rule.name = 'Test Rule'
    >>> rule.algorithm = """ return {
    ...     'add_period': code_evenement() not in {'void_contract', 'hold_contract'},
    ...     }"""
    >>> rule.status = 'validated'
    >>> rule.context = context
    >>> rule.save()
    >>> protocol = Protocol()
    >>> protocol.name = "Basic Protocol"
    >>> protocol.code = "BASIC"
    >>> protocol.third_party_manager = manager
    >>> watched_events = protocol.watched_events.find([
    ...         ('code', 'in', ['activate_contract', 'hold_contract',
    ...                 'unhold_contract', 'void_contract']),
    ...         ])
    >>> protocol.watched_events.extend(watched_events)
    >>> protocol.rule = rule
    >>> protocol.save()

Create Contract::

    >>> config = switch_user('contract_user')
    >>> Contract = Model.get('contract')
    >>> protocol = Model.get('third_party_manager.protocol')(protocol.id)
    >>> coverage = Model.get('offered.option.description')(coverage.id)
    >>> item_description = Model.get('offered.item.description')(item_description.id)
    >>> contract = Contract()
    >>> company = Model.get('company.company')(company.id)
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = dt.date.today()
    >>> product = Model.get('offered.product')(product.id)
    >>> contract.product = product
    >>> contract.contract_number = '123456789'
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> covered_element.item_desc = item_description
    >>> option = covered_element.options.new()
    >>> option.coverage = coverage
    >>> contract.save()
    >>> ProtocolCoverage = Model.get(
    ...     'third_party_manager.protocol-offered.option.description')
    >>> pc = ProtocolCoverage(coverage=option.coverage, protocol=protocol)
    >>> pc.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')

There is now one period::

    >>> contract.reload()
    >>> option, = contract.covered_elements[0].options
    >>> tpp, = option.third_party_periods
    >>> tpp.start_date - dt.date.today() == dt.timedelta(0)
    True
    >>> tpp.end_date is None
    True

Let's suspend the contract five days later::

    >>> config = switch_user('admin')
    >>> SubStatus = Model.get('contract.sub_status')
    >>> hold_status = SubStatus(name='Hold', code='hold', status='hold')
    >>> hold_status.save()
    >>> void_status = SubStatus(name='Void', code='void', status='void')
    >>> void_status.save()
    >>> config = switch_user('contract_user')
    >>> SubStatus = Model.get('contract.sub_status')
    >>> hold_status = SubStatus(hold_status.id)
    >>> config._context['client_defined_date'] = dt.date.today() + dt.timedelta(days=5)
    >>> hold_wizard = Wizard('contract.hold', models=[contract])
    >>> hold_wizard.form.hold_reason = hold_status
    >>> hold_wizard.execute('apply')
    >>> contract.reload()
    >>> option, = contract.covered_elements[0].options
    >>> tpp, = option.third_party_periods
    >>> tpp.start_date - dt.date.today() == dt.timedelta(0)
    True
    >>> (tpp.end_date - dt.date.today()).days == 4
    True

And restart it again 5 days afterwards::

    >>> config._context['client_defined_date'] = dt.date.today() + dt.timedelta(days=10)
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract.reload()
    >>> option, = contract.covered_elements[0].options
    >>> len(option.third_party_periods) == 2
    True
    >>> tpp = option.third_party_periods[-1]
    >>> (tpp.start_date - dt.date.today()).days == 10
    True
    >>> tpp.end_date is None
    True

Test the merging of periods by holding and unholding::

    >>> config._context['client_defined_date'] = dt.date.today() + dt.timedelta(days=20)
    >>> hold_wizard = Wizard('contract.hold', models=[contract])
    >>> hold_wizard.form.hold_reason = hold_status
    >>> hold_wizard.execute('apply')
    >>> contract.reload()
    >>> option, = contract.covered_elements[0].options
    >>> len(option.third_party_periods) == 2
    True
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract.reload()
    >>> option, = contract.covered_elements[0].options
    >>> len(option.third_party_periods) == 2
    True
    >>> tpp = option.third_party_periods[-1]
    >>> (tpp.start_date - dt.date.today()).days == 10
    True
    >>> tpp.end_date is None
    True

Let's void the contract::

    >>> config._context['client_defined_date'] = dt.date.today() + dt.timedelta(days=25)
    >>> void_wizard = Wizard('contract.stop', models=[contract])
    >>> void_wizard.form.status = 'void'
    >>> void_wizard.form.sub_status = SubStatus(void_status.id)
    >>> void_wizard.execute('stop')
    >>> contract.reload()
    >>> option, = contract.covered_elements[0].options
    >>> tpp = option.third_party_periods[-1]
    >>> (tpp.start_date - dt.date.today()).days == 10
    True
    >>> (tpp.end_date - dt.date.today()).days == 25
    True
