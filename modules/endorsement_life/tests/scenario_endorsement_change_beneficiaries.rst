===============================
Endorsement Insurance Scenario
===============================

Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company

Install Modules::

    >>> config = activate_modules('endorsement_life')

Get Models::

    >>> Account = Model.get('account.account')
    >>> AccountKind = Model.get('account.account.type')
    >>> Address = Model.get('party.address')
    >>> Beneficiary = Model.get('contract.option.beneficiary')
    >>> Clause = Model.get('clause')
    >>> Company = Model.get('company.company')
    >>> Contract = Model.get('contract')
    >>> Country = Model.get('country.country')
    >>> CoveredElement = Model.get('contract.covered_element')
    >>> Currency = Model.get('currency.currency')
    >>> CurrencyRate = Model.get('currency.currency.rate')
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> EndorsementDefinitionPartRelation = Model.get(
    ...     'endorsement.definition-endorsement.part')
    >>> EndorsementPart = Model.get('endorsement.part')
    >>> Field = Model.get('ir.model.field')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> Party = Model.get('party.party')
    >>> Option = Model.get('contract.option')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Product = Model.get('offered.product')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> User = Model.get('res.user')
    >>> Insurer = Model.get('insurer')

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

    >>> _ = create_company(currency=currency)
    >>> company = get_company()

Reload the context::

    >>> config._context = User.get_preferences(True, config.context)
    >>> config._context['company'] = company.id

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
    >>> receivable_account.party_required = True
    >>> receivable_account.reconcile = True
    >>> receivable_account.type = receivable_account_kind
    >>> receivable_account.company = company
    >>> receivable_account.save()
    >>> payable_account = Account()
    >>> payable_account.name = 'Account Payable'
    >>> payable_account.code = 'account_payable'
    >>> payable_account.party_required = True
    >>> payable_account.type = payable_account_kind
    >>> payable_account.company = company
    >>> payable_account.save()

Create Beneficiary Clauses::

    >>> clause1 = Clause()
    >>> clause1.name = 'Beneficiary Clause 1'
    >>> clause1.content = 'Beneficiary Clause 1 contents'
    >>> clause1.kind = 'beneficiary'
    >>> clause1.save()
    >>> clause2 = Clause()
    >>> clause2.name = 'Beneficiary Clause 2'
    >>> clause2.content = 'Beneficiary Clause 2 contents'
    >>> clause2.kind = 'beneficiary'
    >>> clause2.customizable = True
    >>> clause2.save()

Create Insurer::

    >>> insurer = Insurer()
    >>> insurer.party = Party()
    >>> insurer.party.name = 'Insurer'
    >>> insurer.party.account_receivable = receivable_account
    >>> insurer.party.account_payable = payable_account
    >>> insurer.party.save()
    >>> insurer.save()

Create Item Description::

    >>> item_description = ItemDescription()
    >>> item_description.name = 'Test Item Description'
    >>> item_description.code = 'test_item_description'
    >>> item_description.kind = 'person'
    >>> item_description.save()

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
    >>> coverage.family = 'life'
    >>> coverage.inurance_kind = 'death'
    >>> coverage.start_date = product_start_date
    >>> coverage.item_desc = item_description
    >>> coverage.insurer = insurer
    >>> coverage.beneficiaries_clauses.append(clause1)
    >>> coverage.beneficiaries_clauses.append(clause2)
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

Create Change Beneficiaries::

    >>> change_beneficiaries_part, = EndorsementPart.find([(
    ...     'code', '=', 'change_beneficiary')])
    >>> change_beneficiaries = EndorsementDefinition()
    >>> change_beneficiaries.name = 'Manage Beneficiaries'
    >>> change_beneficiaries.code = 'change_beneficiary'
    >>> change_beneficiaries.ordered_endorsement_parts.append(
    ...     EndorsementDefinitionPartRelation(
    ...         endorsement_part=change_beneficiaries_part))
    >>> change_beneficiaries.save()

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
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.contract_number = '123456'
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> covered_element.item_desc = item_description
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> option.has_beneficiary_clause is True
    True
    >>> option.beneficiary_clause = clause1
    >>> beneficiary = option.beneficiaries.new()
    >>> beneficiary.party = subscriber
    >>> beneficiary.address = subscriber.addresses[0]
    >>> contract.end_date = datetime.date(2030, 12, 1)
    >>> contract.save()
    >>> Contract.write([contract.id], {
    ...         'status': 'active',
    ...         }, config.context)
    >>> my_option = contract.covered_elements[0].options[0]
    >>> len(my_option.beneficiaries) == 1
    True

New Endorsement::

    >>> new_payment_date = datetime.date(2014, 7, 1)
    >>> new_end_date = datetime.date(2031, 1, 31)
    >>> new_increment_date = datetime.date(2023, 2, 22)
    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = change_beneficiaries
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = new_increment_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.current_options[0] = new_endorsement.form.all_options[0]
    >>> new_option = new_endorsement.form.all_options[0]
    >>> new_option.beneficiary_clause == clause1
    True
    >>> len(new_option.beneficiaries) == 1
    True
    >>> new_option.beneficiary_clause = clause2
    >>> new_beneficiary = new_option.beneficiaries.new()
    >>> new_beneficiary.beneficiary[0].party = luigi
    >>> new_beneficiary.beneficiary[0].address = luigi.addresses[0]
    >>> new_endorsement.execute('manage_beneficiaries_next')
    >>> new_endorsement.execute('apply_endorsement')

Test result::

    >>> contract = Contract(contract.id)
    >>> option = contract.covered_elements[0].options[0]
    >>> len(option.beneficiaries) == 2
    True
    >>> option.beneficiary_clause == clause2
    True
