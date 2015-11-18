============================================
Full Contract Revision Endorsement Scenario
============================================

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
    >>> full_contract_revision_module = Module.find([
    ...         ('name', '=', 'endorsement_full_contract_revision')])[0]
    >>> Module.install([full_contract_revision_module.id], config.context)
    >>> wizard = Wizard('ir.module.install_upgrade')
    >>> wizard.execute('upgrade')

Get Models::

    >>> Action = Model.get('ir.action')
    >>> Company = Model.get('company.company')
    >>> Contract = Model.get('contract')
    >>> Country = Model.get('country.country')
    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> Endorsement = Model.get('endorsement')
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> IrModel = Model.get('ir.model')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Party = Model.get('party.party')
    >>> Process = Model.get('process')
    >>> ProcessAction = Model.get('process.action')
    >>> ProcessStep = Model.get('process.step')
    >>> Product = Model.get('offered.product')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> User = Model.get('res.user')

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)
    >>> new_contract_start_date = datetime.date(2014, 10, 21)

Create or fetch Currency::

    >>> currencies = Currency.find([('code', '=', 'USD')])
    >>> if not currencies:
    ...     currency = Currency(name='US Dollar', symbol=u'$', code='USD',
    ...         rounding=Decimal('0.01'), mon_grouping='[]',
    ...         mon_decimal_point='.')
    ...     currency.save()
    ...     CurrencyRate(date=today + relativedelta(month=1, day=1),
    ...         rate=Decimal('1.0'), currency=currency).save()
    ... else:
    ...     currency, = currencies

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
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.start_date = product_start_date
    >>> coverage.save()
    >>> product = Product()
    >>> product.company = company
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
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
    >>> subscriber.birth_date = datetime.date(1980, 10, 14)
    >>> subscriber.save()

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.subscriber = subscriber
    >>> contract.quote_number = 'Initial Number'
    >>> contract.save()

Start Endorsement::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = EndorsementDefinition.find([
    ...         ('code', '=', 'full_contract_revision')])[0]
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = new_contract_start_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.current_start_date == contract_start_date
    True
    >>> new_endorsement.form.start_date == new_contract_start_date
    True
    >>> new_endorsement.execute('full_contract_revision_next')

Modify Contract::

    >>> new_endorsement, = Endorsement.find([])
    >>> new_endorsement.state == 'in_progress'
    True
    >>> contract = Contract(contract.id)
    >>> contract.start_date == new_contract_start_date
    True
    >>> contract.quote_number == 'Initial Number'
    True
    >>> contract.current_state.id == process.all_steps[0].id
    True
    >>> contract.quote_number = 'New Number'
    >>> contract.save()

Revert Current process::

    >>> Contract.revert_current_endorsement([contract.id], {})
    'close'
    >>> contract = Contract(contract.id)
    >>> contract.quote_number == 'Initial Number'
    True
    >>> Endorsement.find([]) == []
    True
    >>> contract.start_date == contract_start_date
    True

Restart Endorsement (Same as before)::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = EndorsementDefinition.find([
    ...         ('code', '=', 'full_contract_revision')])[0]
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = new_contract_start_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.current_start_date == contract_start_date
    True
    >>> new_endorsement.form.start_date == new_contract_start_date
    True
    >>> new_endorsement.execute('full_contract_revision_next')

Modify Contract::

    >>> contract = Contract(contract.id)
    >>> contract.quote_number = 'New Number'
    >>> contract.contract_number = 'New Number'
    >>> contract.status = 'active'
    >>> contract.save()
    >>> end_process, = Action.find([
    ...         ('xml_id', '=', 'process_cog.act_end_process')])
    >>> Contract._proxy._button_next_1([contract.id], {}) == end_process.id
    True

Check Application::

    >>> new_endorsement, = Endorsement.find([])
    >>> new_endorsement.state == 'applied'
    True
    >>> contract = Contract(contract.id)
    >>> contract.quote_number == 'New Number'
    True
    >>> contract.current_state is None
    True
