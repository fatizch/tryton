
Imports::

    >>> import datetime
    >>> import os
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.contract_noemie import batch as noemie_batch

Install Modules::

    >>> config = activate_modules(['contract_noemie', 'batch_launcher'])

Get Models::

    >>> Account = Model.get('account.account')
    >>> AccountKind = Model.get('account.account.type')
    >>> Company = Model.get('company.company')
    >>> Configuration = Model.get('account.configuration')
    >>> ConfigurationTaxRounding = Model.get('account.configuration.tax_rounding')
    >>> Contract = Model.get('contract')
    >>> Country = Model.get('country.country')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> Insurer = Model.get('insurer')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> Option = Model.get('contract.option')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Party = Model.get('party.party')
    >>> Product = Model.get('offered.product')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> User = Model.get('res.user')

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 1)

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
    >>> product_account_kind.save()
    >>> receivable_account_kind = AccountKind()
    >>> receivable_account_kind.name = 'Receivable Account Kind'
    >>> receivable_account_kind.company = company
    >>> receivable_account_kind.save()
    >>> payable_account_kind = AccountKind()
    >>> payable_account_kind.name = 'Payable Account Kind'
    >>> payable_account_kind.company = company
    >>> payable_account_kind.save()
    >>> other_account_kind = AccountKind()
    >>> other_account_kind.name = 'Other Account Kind'
    >>> other_account_kind.company = company
    >>> other_account_kind.save()

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
    >>> payable_account_insurer = Account()
    >>> payable_account_insurer.name = 'Account Payable Insurer'
    >>> payable_account_insurer.code = 'account_payable_insurer'
    >>> payable_account_insurer.kind = 'payable'
    >>> payable_account_insurer.party_required = True
    >>> payable_account_insurer.type = other_account_kind
    >>> payable_account_insurer.company = company
    >>> payable_account_insurer.save()

Create Item Description::

    >>> item_description = ItemDescription()
    >>> item_description.name = 'Test Item Description'
    >>> item_description.code = 'test_item_description'
    >>> item_description.kind = 'person'
    >>> item_description.is_noemie = True
    >>> item_description.save()

Create Insurer::

    >>> insurer = Insurer()
    >>> insurer.party = Party()
    >>> insurer.party.name = 'Insurer'
    >>> insurer.party.account_receivable = receivable_account
    >>> insurer.party.account_payable = payable_account_insurer
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
    >>> product = Product()
    >>> coverage = OptionDescription()
    >>> coverage.insurer = insurer
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.item_desc = item_description
    >>> coverage.start_date = product_start_date
    >>> coverage.account_for_billing = product_account
    >>> coverage.save()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
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

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.initial_start_date = datetime.date(2014, 3, 1)
    >>> contract.product = product
    >>> contract.status = 'quote'
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> covered_element.item_desc.is_noemie = True
    >>> covered_element.item_desc.save()
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> contract.save()
    >>> IrModel = Model.get('ir.model')
    >>> noemie_flow_batch, = IrModel.find([
    ...     ('model', '=', 'contract.noemie.flow.batch')])
    >>> module_file = noemie_batch.__file__
    >>> module_folder = os.path.dirname(module_file)
    >>> def import_noemie_flow(file_name):
    ...     launcher = Wizard('batch.launcher')
    ...     launcher.form.batch = noemie_flow_batch
    ...     dir_ = os.path.join(module_folder, 'tests_imports/')
    ...     out_dir = os.path.join(module_folder, 'tests_exports/')
    ...     file_path = dir_ + file_name
    ...     for i in range(0, len(launcher.form.parameters)):
    ...         if launcher.form.parameters[i].code == 'in_directory':
    ...             launcher.form.parameters[i].value = file_path
    ...         elif launcher.form.parameters[i].code == 'out_directory':
    ...             launcher.form.parameters[i].value = out_dir
    ...     launcher.execute('process')
    ...     return
    >>> _ = import_noemie_flow('NOEASS.FIC8132')
    >>> CoveredElement = Model.get('contract.covered_element')
    >>> covered_ele, = CoveredElement.find(['party.code', '=', subscriber.code])
    >>> covered_ele.is_noemie
    True
    >>> covered_ele.noemie_return_code == '33'
    True
    >>> covered_ele.noemie_status == 'acquitted'
    True
    >>> covered_ele.noemie_update_date == datetime.date(2019, 2, 17)
    True
