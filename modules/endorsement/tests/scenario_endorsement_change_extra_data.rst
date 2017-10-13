=========================================
Contract Extra Data Endorsement Scenario
=========================================

Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.coog_core.test_framework import execute_test_case, \
    ...     switch_user

Install Modules::

    >>> config = activate_modules('endorsement')

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)
    >>> effective_date = datetime.date(2014, 10, 21)

Create or fetch Currency::

    >>> currency = get_currency(code='EUR')

Create or fetch Country::

    >>> Country = Model.get('country.country')
    >>> countries = Country.find([('code', '=', 'FR')])
    >>> if not countries:
    ...     country = Country(name='France', code='FR')
    ...     country.save()
    ... else:
    ...     country, = countries

Create Company::

    >>> currency = get_currency(code='EUR')
    >>> _ = create_company(currency=currency)
    >>> execute_test_case('authorizations_test_case')
    >>> config = switch_user('product_user')
    >>> company = get_company()
    >>> currency = get_currency(code='EUR')

Create Test ExtraData::

    >>> ExtraData = Model.get('extra_data')
    >>> extra_data = ExtraData()
    >>> extra_data.name = 'formula'
    >>> extra_data.code = 'formula'
    >>> extra_data.type_ = 'integer'
    >>> extra_data.string = 'formula'
    >>> extra_data.kind = 'contract'
    >>> extra_data.save()

Create Product::

    >>> SequenceType = Model.get('ir.sequence.type')
    >>> Sequence = Model.get('ir.sequence')
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
    >>> OptionDescription = Model.get('offered.option.description')
    >>> coverage = OptionDescription()
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.start_date = product_start_date
    >>> coverage.save()
    >>> Product = Model.get('offered.product')
    >>> product = Product()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.coverages.append(coverage)
    >>> product.extra_data_def.append(extra_data)
    >>> product.save()

Create Change Extra Data Endorsement::

    >>> EndorsementPart = Model.get('endorsement.part')
    >>> change_extra_data_part = EndorsementPart()
    >>> change_extra_data_part.name = 'Change Extra Data'
    >>> change_extra_data_part.code = 'change_extra_data'
    >>> change_extra_data_part.kind = 'extra_data'
    >>> change_extra_data_part.view = 'change_contract_extra_data'
    >>> change_extra_data_part.save()
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> change_extra_data = EndorsementDefinition()
    >>> change_extra_data.name = 'Change Extra Data'
    >>> change_extra_data.code = 'change_extra_data'
    >>> EndorsementDefinitionPartRelation = Model.get(
    ...     'endorsement.definition-endorsement.part')
    >>> change_extra_data.ordered_endorsement_parts.append(
    ...     EndorsementDefinitionPartRelation(endorsement_part=change_extra_data_part))
    >>> change_extra_data.save()
    >>> config = switch_user('contract_user')
    >>> company = get_company()
    >>> currency = get_currency(code='EUR')

Create Test Contract::

    >>> Contract = Model.get('contract')
    >>> Product = Model.get('offered.product')
    >>> product = Product(product.id)
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.contract_number = '1111'
    >>> contract.status = 'active'
    >>> contract.save()
    >>> contract.extra_datas[0].extra_data_values = {'formula': 1}
    >>> contract.extra_datas[0].date = None
    >>> contract.extra_datas[0].save()
    >>> len(contract.extra_datas) == 1
    True
    >>> contract.extra_datas[0].extra_data_values == {'formula': 1}
    True

New Endorsement::

    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> change_extra_data = EndorsementDefinition(change_extra_data.id)
    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> new_endorsement.form.endorsement_definition = change_extra_data
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = effective_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.current_extra_data_date is None
    True
    >>> new_endorsement.form.new_extra_data_date == effective_date
    True
    >>> new_endorsement.form.new_extra_data = {'formula': 2}
    >>> new_endorsement.execute('change_contract_extra_data_next')
    >>> new_endorsement.execute('apply_endorsement')
    >>> contract.save()
    >>> len(contract.extra_datas) == 2
    True
    >>> contract.extra_datas[0].extra_data_values == {'formula': 1}
    True
    >>> contract.extra_datas[0].date is None
    True
    >>> contract.extra_datas[1].extra_data_values == {'formula': 2}
    True
    >>> contract.extra_datas[1].date == effective_date
    True
    >>> Endorsement = Model.get('endorsement')
    >>> good_endorsement, = Endorsement.find([
    ...         ('contracts', '=', contract.id)])
    >>> Endorsement.cancel([good_endorsement.id], config._context)
    >>> contract.save()
    >>> len(contract.extra_datas) == 1
    True
    >>> contract.extra_datas[0].extra_data_values == {'formula': 1}
    True
    >>> contract.extra_datas[0].date is None
    True

New Endorsement::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = change_extra_data
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = contract_start_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.current_extra_data_date is None
    True
    >>> new_endorsement.form.new_extra_data_date is None
    True
    >>> new_endorsement.form.new_extra_data = {'formula': 3}
    >>> new_endorsement.execute('change_contract_extra_data_next')
    >>> new_endorsement.execute('apply_endorsement')
    >>> contract.save()
    >>> len(contract.extra_datas) == 1
    True
    >>> contract.extra_datas[0].extra_data_values == {'formula': 3}
    True
    >>> contract.extra_datas[0].date is None
    True
