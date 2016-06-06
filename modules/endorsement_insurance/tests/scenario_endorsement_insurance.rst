===============================
Endorsement Insurance Scenario
===============================

Imports::

    >>> import datetime
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.currency.tests.tools import get_currency

Init Database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install Modules::

    >>> Module = Model.get('ir.module')
    >>> endorsement_module = Module.find([('name', '=', 'endorsement_insurance')])[0]
    >>> Module.install([endorsement_module.id], config.context)
    >>> wizard = Wizard('ir.module.install_upgrade')
    >>> wizard.execute('upgrade')

Get Models::

    >>> Account = Model.get('account.account')
    >>> AccountKind = Model.get('account.account.type')
    >>> Company = Model.get('company.company')
    >>> Contract = Model.get('contract')
    >>> Country = Model.get('country.country')
    >>> Endorsement = Model.get('endorsement')
    >>> EndorsementContract = Model.get('endorsement.contract')
    >>> EndorsementContractField = Model.get('endorsement.contract.field')
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> EndorsementDefinitionPartRelation = Model.get(
    ...     'endorsement.definition-endorsement.part')
    >>> EndorsementPart = Model.get('endorsement.part')
    >>> ExclusionKind = Model.get('offered.exclusion')
    >>> Field = Model.get('ir.model.field')
    >>> Insurer = Model.get('insurer')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> ManageExclusionDisplayer = Model.get('contract.manage_exclusions.exclusion')
    >>> MethodDefinition = Model.get('ir.model.method')
    >>> Option = Model.get('contract.option')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Party = Model.get('party.party')
    >>> Product = Model.get('offered.product')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> SubStatus = Model.get('contract.sub_status')
    >>> User = Model.get('res.user')

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)
    >>> endorsement_effective_date = datetime.date(2014, 10, 21)

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
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.start_date = product_start_date
    >>> coverage.item_desc = item_description
    >>> coverage.insurer = insurer
    >>> coverage.subscription_behaviour = 'optional'
    >>> coverage.save()
    >>> product = Product()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.coverages.append(coverage)
    >>> product.save()

Create SubStatus::

    >>> termination_status, = SubStatus.find([('code', '=', 'terminated')])

Create Remove Option Endorsement::

    >>> remove_option_part = EndorsementPart()
    >>> remove_option_part.name = 'Remove Option'
    >>> remove_option_part.code = 'remove_option'
    >>> remove_option_part.kind = 'covered_element'
    >>> remove_option_part.view = 'remove_option'
    >>> remove_option_part.save()
    >>> remove_option = EndorsementDefinition()
    >>> remove_option.name = 'Remove Option'
    >>> remove_option.code = 'remove_option'
    >>> remove_option.ordered_endorsement_parts.append(
    ...     EndorsementDefinitionPartRelation(endorsement_part=remove_option_part))
    >>> remove_option.save()

Create Manage Exclusions Endorsement::

    >>> exclusion_part, = EndorsementPart.find([('code', '=', 'manage_exclusions')])
    >>> manage_exclusions = EndorsementDefinition()
    >>> manage_exclusions.name = 'Manage Exclusions'
    >>> manage_exclusions.code = 'manage_exclusions'
    >>> manage_exclusions.ordered_endorsement_parts.append(
    ...     EndorsementDefinitionPartRelation(endorsement_part=exclusion_part))
    >>> manage_exclusions.save()

Create exclusion kinds::

    >>> exclusion_1 = ExclusionKind(name='Exclusion 1', code='exclusion_1',
    ...     text='Exclusion 1')
    >>> exclusion_1.save()
    >>> exclusion_2 = ExclusionKind(name='Exclusion 2', code='exclusion_2',
    ...     text='Exclusion 2')
    >>> exclusion_2.save()

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

Create Other Insured::

    >>> luigi = Party()
    >>> luigi.name = 'Vercotti'
    >>> luigi.first_name = 'Luigi'
    >>> luigi.is_person = True
    >>> luigi.gender = 'male'
    >>> luigi.account_receivable = receivable_account
    >>> luigi.account_payable = payable_account
    >>> luigi.birth_date = datetime.date(1965, 10, 14)
    >>> luigi.save()

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'active'
    >>> contract.contract_number = '12345'
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> covered_element.item_desc = item_description
    >>> option = covered_element.options.new()
    >>> option.coverage = coverage
    >>> covered_element2 = contract.covered_elements.new()
    >>> covered_element2.party = luigi
    >>> covered_element2.item_desc = item_description
    >>> option2 = covered_element2.options.new()
    >>> option2.coverage = coverage
    >>> option2.exclusions.append(exclusion_1)
    >>> contract.subscriber = subscriber
    >>> contract.save()
    >>> contract.covered_elements[0].options[0].end_date == None
    True
    >>> contract.covered_elements[1].options[0].end_date == None
    True

New Manage Exclusions Endorsement::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = manage_exclusions
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = endorsement_effective_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.contract.contract.id == contract.id
    True
    >>> len(new_endorsement.form.current_options) == 2
    True
    >>> len(new_endorsement.form.current_options[0].exclusions) == 0
    True
    >>> len(new_endorsement.form.current_options[1].exclusions) == 1
    True
    >>> new_endorsement.form.current_options[1].exclusions[0].action = 'removed'
    >>> new_endorsement.form.current_options[0].exclusions.append(
    ...     ManageExclusionDisplayer(exclusion=exclusion_2.id))
    >>> new_endorsement.form.current_options[0].exclusions[0].action == 'added'
    True
    >>> new_endorsement.form.current_options[0].exclusions.append(
    ...     ManageExclusionDisplayer(exclusion=exclusion_1.id, action='removed'))
    >>> new_endorsement.execute('manage_exclusions_next')
    >>> new_endorsement.execute('summary_previous')
    >>> new_endorsement.form.contract.contract.id == contract.id
    True
    >>> len(new_endorsement.form.current_options) == 2
    True
    >>> len(new_endorsement.form.current_options[0].exclusions) == 1
    True
    >>> len(new_endorsement.form.current_options[1].exclusions) == 1
    True
    >>> new_endorsement.form.current_options[0].exclusions[0].action == 'added'
    True
    >>> new_endorsement.form.current_options[1].exclusions[0].action == 'removed'
    True
    >>> new_endorsement.execute('manage_exclusions_next')
    >>> new_endorsement.execute('apply_endorsement')
    >>> contract = Contract(contract.id)
    >>> [x.code for x in contract.covered_elements[0].options[0].exclusions] == [
    ...     'exclusion_2']
    True
    >>> len(contract.covered_elements[1].options[0].exclusions) == 0
    True
    >>> endorsement_last, = Endorsement.find([], order=[('create_date', 'DESC')],
    ...     limit=1)
    >>> endorsement_last.click('cancel')
    >>> contract = Contract(contract.id)
    >>> len(contract.covered_elements[0].options[0].exclusions) == 0
    True
    >>> [x.code for x in contract.covered_elements[1].options[0].exclusions] == [
    ...     'exclusion_1']
    True

New Remove Option Endorsement::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = remove_option
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = endorsement_effective_date
    >>> new_endorsement.execute('start_endorsement')
    >>> my_option = new_endorsement.form.options[0].option
    >>> len(new_endorsement.form.options) == 2
    True
    >>> to_remove, = [x for x in new_endorsement.form.options if
    ...     x.covered_element.party.name == 'Vercotti']
    >>> to_remove.action = 'terminated'
    >>> to_remove.sub_status = termination_status
    >>> new_endorsement.execute('remove_option_next')
    >>> new_endorsement.execute('apply_endorsement')
    >>> contract.save()
    >>> option, = Option.find([('covered_element.party.name', '=', 'Doe')])
    >>> option2, = Option.find([('covered_element.party.name', '=', 'Vercotti')])
    >>> option2.end_date == endorsement_effective_date
    True
    >>> option2.sub_status == termination_status
    True
    >>> option.end_date == None
    True
    >>> option.sub_status == None
    True
    >>> endorsement_last, = Endorsement.find([], order=[('create_date', 'DESC')],
    ...     limit=1)
    >>> endorsement_last.click('cancel')
    >>> contract = Contract(contract.id)
    >>> option, = Option.find([('covered_element.party.name', '=', 'Doe')])
    >>> option2, = Option.find([('covered_element.party.name', '=', 'Vercotti')])
    >>> option2.end_date == None
    True
    >>> option2.sub_status == None
    True
    >>> option.end_date == None
    True
    >>> option.sub_status == None
    True
