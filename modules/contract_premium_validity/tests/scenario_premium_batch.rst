
Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from dateutil.relativedelta import relativedelta
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency

Install Modules::

    >>> config = activate_modules(['contract_premium_validity', 'batch_launcher'])

Get Modules::

    >>> Account = Model.get('account.account')
    >>> AccountKind = Model.get('account.account.type')
    >>> BatchParameter = Model.get('batch.launcher.parameter')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Contract = Model.get('contract')
    >>> Country = Model.get('country.country')
    >>> Insurer = Model.get('insurer')
    >>> IrModel = Model.get('ir.model')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> OptionDescriptionEndingRule = Model.get(
    ...     'offered.option.description.ending_rule')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> Premium = Model.get('contract.premium')
    >>> PremiumEndingRule = Model.get('offered.product.premium_validity_rule')
    >>> Product = Model.get('offered.product')
    >>> ProductPremiumDate = Model.get('offered.product.premium_date')
    >>> RuleEngine = Model.get('rule_engine')
    >>> RuleEngineContext = Model.get('rule_engine.context')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> SubStatus = Model.get('contract.sub_status')

Constants::

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
    >>> other_account_kind = AccountKind()
    >>> other_account_kind.name = 'Other Account Kind'
    >>> other_account_kind.company = company
    >>> other_account_kind.statement = 'balance'
    >>> other_account_kind.payable = True
    >>> other_account_kind.save()
    >>> tax_account_kind = AccountKind()
    >>> tax_account_kind.name = 'Tax Account Kind'
    >>> tax_account_kind.company = company
    >>> tax_account_kind.statement = 'balance'
    >>> tax_account_kind.save()

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
    >>> receivable_account.type = receivable_account_kind
    >>> receivable_account.party_required = True
    >>> receivable_account.reconcile = True
    >>> receivable_account.company = company
    >>> receivable_account.save()
    >>> payable_account = Account()
    >>> payable_account.name = 'Account Payable'
    >>> payable_account.code = 'account_payable'
    >>> payable_account.type = payable_account_kind
    >>> payable_account.party_required = True
    >>> payable_account.company = company
    >>> payable_account.save()
    >>> tax_account = Account()
    >>> tax_account.name = 'Main tax'
    >>> tax_account.code = 'main_tax'
    >>> tax_account.company = company
    >>> tax_account.type = tax_account_kind
    >>> tax_account.save()
    >>> payable_account_insurer = Account()
    >>> payable_account_insurer.name = 'Account Payable Insurer'
    >>> payable_account_insurer.code = 'account_payable_insurer'
    >>> payable_account_insurer.type = other_account_kind
    >>> payable_account_insurer.party_required = True
    >>> payable_account_insurer.company = company
    >>> payable_account_insurer.save()

Create billing mode::

    >>> payment_term = PaymentTerm()
    >>> payment_term.name = 'direct'
    >>> payment_term.lines.append(PaymentTermLine())
    >>> payment_term.save()
    >>> freq_yearly = BillingMode()
    >>> freq_yearly.name = 'Yearly'
    >>> freq_yearly.code = 'yearly'
    >>> freq_yearly.frequency = 'yearly'
    >>> freq_yearly.allowed_payment_terms.append(payment_term)
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
    >>> insurer.party.account_payable = payable_account_insurer
    >>> insurer.party.save()
    >>> insurer.save()

Rule context::

    >>> rule_context = RuleEngineContext(1)

Termination rule::

    >>> termination_rule, = RuleEngine.find([('short_name', '=',
    ...     'option_end_date_rule')])
    >>> termination_rule.save()

Create Product::

    >>> sequence_code = SequenceType()
    >>> sequence_code.name = 'Product sequence'
    >>> sequence_code.code = 'contract'
    >>> sequence_code.company = company
    >>> sequence_code.save()
    >>> contract_sequence = Sequence()
    >>> contract_sequence.name = 'Contract Sequennce'
    >>> contract_sequence.code = sequence_code.code
    >>> contract_sequence.company = company
    >>> contract_sequence.save()
    >>> quote_sequence_code = SequenceType()
    >>> quote_sequence_code.name = 'Product sequence'
    >>> quote_sequence_code.code = 'quote'
    >>> quote_sequence_code.coompany = company
    >>> quote_sequence_code.save()
    >>> quote_sequence = Sequence()
    >>> quote_sequence.name = 'Quote Sequence'
    >>> quote_sequence.code = quote_sequence_code.code
    >>> quote_sequence.company = company
    >>> quote_sequence.save()
    >>> product = Product()
    >>> sub_status, = SubStatus.find([('code', '=', 'reached_end_date')])
    >>> sub_status.save()
    >>> coverage = OptionDescription()
    >>> coverage.insurer = insurer
    >>> coverage.company = company
    >>> coverage.currency = currency
    >>> coverage.name = 'Test Coverage'
    >>> coverage.code = 'test_coverage'
    >>> coverage.item_desc = item_description
    >>> coverage.start_date = product_start_date
    >>> coverage.account_for_billing = product_account
    >>> coverage.allow_subscribe_coverage_multiple_times = True
    >>> default_context, = RuleEngineContext.find([('name', '=', 'Context par défaut')])
    >>> algo = '\n'.join(['return Decimal(100) * date_de_calcul().month'])
    >>> premium_rule = RuleEngine()
    >>> premium_rule.name = 'yearly_100'
    >>> premium_rule.short_name = 'yearly_100'
    >>> premium_rule.algorithm = algo
    >>> premium_rule.status = 'validated'
    >>> premium_rule.type_ = 'premium'
    >>> premium_rule.context = default_context
    >>> premium_rule.save()
    >>> rule = coverage.premium_rules.new()
    >>> rule.frequency = 'yearly'
    >>> rule.rule = premium_rule
    >>> premium_rule.save()
    >>> coverage.save()
    >>> ending_rule = OptionDescriptionEndingRule()
    >>> ending_rule.automatic_sub_status = sub_status
    >>> ending_rule.coverage = coverage
    >>> ending_rule.rule = termination_rule
    >>> ending_rule.rule_extra_data = {'age_kind': 'real', 'given_day': None,
    ...     'given_month': None, 'max_age_for_option': 75}
    >>> ending_rule.save()
    >>> len(coverage.ending_rule)
    1
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.coverages.append(coverage)
    >>> product.billing_rules[-1].billing_modes.append(freq_yearly)
    >>> product.save()

Create Premium Ending Rule::

    >>> end_rule = RuleEngine()
    >>> end_rule.algorithm = (
    ...     'end_date=ajouter_mois(aujourd_hui(),1,True)\n'
    ...     'next_month=end_date.replace(day=28)+datetime.timedelta(days=4)\n'
    ...     'last_day=next_month-datetime.timedelta(days=next_month.day)\n'
    ...     'return last_day'
    ...     )
    >>> end_rule.context = rule_context
    >>> end_rule.name = 'pemium end rule'
    >>> end_rule.rec_name = 'premium end rule'
    >>> end_rule.result_type = 'date'
    >>> end_rule.short_name = 'premium_end_rule'
    >>> end_rule.status = 'validated'
    >>> end_rule.type_ = 'ending'
    >>> end_rule.save()
    >>> premium_ending_rule = PremiumEndingRule()
    >>> premium_ending_rule.product = product
    >>> premium_ending_rule.rule = end_rule
    >>> premium_ending_rule.save()

Create Product Premium Date::

    >>> premium_date = ProductPremiumDate()
    >>> premium_date.product = product
    >>> premium_date.type_ = 'monthly_on_start_date'
    >>> premium_date.save()
    >>> product.premium_dates.append(premium_date)
    >>> product.save()

Create Subscriber::

    >>> subscriber = Party()
    >>> subscriber.name = 'Doe'
    >>> subscriber.first_name = 'John'
    >>> subscriber.is_person = True
    >>> subscriber.gender = 'male'
    >>> subscriber.account_receivable = receivable_account
    >>> subscriber.account_payable = payable_account
    >>> subscriber.birth_date = datetime.date(1990, 10, 14)
    >>> subscriber.save()

Create Test Contract::

    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'quote'
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...     billing_mode=freq_yearly, payment_term=payment_term))
    >>> covered_element = contract.covered_elements.new()
    >>> covered_element.party = subscriber
    >>> option = covered_element.options[0]
    >>> option.coverage = coverage
    >>> contract.save()
    >>> config._context['client_defined_date'] = contract_start_date
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> contract.end_date
    datetime.date(2066, 10, 13)
    >>> contract.premium_validity_end
    datetime.date(2014, 5, 31)
    >>> len(contract.all_premiums)
    2
    >>> contract.all_premiums[-1].start
    datetime.date(2014, 5, 1)
    >>> contract.all_premiums[-1].end
    datetime.date(2014, 5, 31)
    >>> contract.all_premiums[-2].start
    datetime.date(2014, 4, 1)
    >>> contract.all_premiums[-2].end
    datetime.date(2014, 4, 30)
    >>> config._context['client_defined_date'] = contract_start_date + \
    ...     relativedelta(days=2)
    >>> batch, = IrModel.find([
    ...     ('model', '=', 'contract.premium.calculate'),
    ...     ])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = batch
    >>> treatment_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'treatment_date']
    >>> treatment_date_param.value = str(config._context['client_defined_date'])
    >>> from_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'from_date']
    >>> from_date_param.value = str(config._context['client_defined_date'])
    >>> launcher.execute('process')
    >>> contract.save()
    >>> contract.premium_validity_end
    datetime.date(2014, 5, 31)
    >>> len(contract.all_premiums)
    2
    >>> contract.all_premiums[-1].start
    datetime.date(2014, 5, 1)
    >>> contract.all_premiums[-1].end
    datetime.date(2014, 5, 31)
    >>> contract.all_premiums[-2].start
    datetime.date(2014, 4, 1)
    >>> contract.all_premiums[-2].end
    datetime.date(2014, 4, 30)
    >>> config._context['client_defined_date'] = contract_start_date + \
    ...     relativedelta(months=3)
    >>> batch, = IrModel.find([
    ...     ('model', '=', 'contract.premium.calculate'),
    ...     ])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = batch
    >>> treatment_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'treatment_date']
    >>> treatment_date_param.value = str(config._context['client_defined_date'])
    >>> from_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'from_date']
    >>> from_date_param.value = str(config._context['client_defined_date'])
    >>> launcher.execute('process')
    >>> contract.save()
    >>> contract.premium_validity_end
    datetime.date(2014, 5, 31)
    >>> len(contract.all_premiums)
    2
    >>> config._context['client_defined_date'] = contract_start_date + \
    ...     relativedelta(months=2)
    >>> batch, = IrModel.find([
    ...     ('model', '=', 'contract.premium.calculate'),
    ...     ])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = batch
    >>> treatment_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'treatment_date']
    >>> treatment_date_param.value = str(config._context['client_defined_date'])
    >>> from_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'from_date']
    >>> from_date_param.value = str(config._context['client_defined_date'])
    >>> launcher.execute('process')
    >>> contract.save()
    >>> contract.premium_validity_end
    datetime.date(2014, 5, 31)
    >>> len(contract.all_premiums)
    2
    >>> config._context['client_defined_date'] = contract_start_date + \
    ...     relativedelta(months=1)
    >>> batch, = IrModel.find([
    ...     ('model', '=', 'contract.premium.calculate'),
    ...     ])
    >>> launcher = Wizard('batch.launcher')
    >>> launcher.form.batch = batch
    >>> treatment_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'treatment_date']
    >>> treatment_date_param.value = str(config._context['client_defined_date'])
    >>> from_date_param, = [
    ...     p for p in launcher.form.parameters if p.code == 'from_date']
    >>> from_date_param.value = str(config._context['client_defined_date'])
    >>> launcher.execute('process')
    >>> contract.save()
    >>> contract.premium_validity_end
    datetime.date(2014, 6, 30)
    >>> len(contract.all_premiums)
    3
    >>> contract.all_premiums[-1].start
    datetime.date(2014, 6, 1)
    >>> contract.all_premiums[-1].end
    datetime.date(2014, 6, 30)
    >>> contract.all_premiums[-2].start
    datetime.date(2014, 5, 1)
    >>> contract.all_premiums[-2].end
    datetime.date(2014, 5, 31)
    >>> contract.all_premiums[-3].start
    datetime.date(2014, 4, 1)
    >>> contract.all_premiums[-3].end
    datetime.date(2014, 4, 30)
