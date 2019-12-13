
Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency

Install Modules::

    >>> config = activate_modules('contract_premium_modification')

Get Modules::

    >>> Account = Model.get('account.account')
    >>> AccountInvoice = Model.get('account.invoice')
    >>> AccountKind = Model.get('account.account.type')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> CommercialDiscount = Model.get('commercial_discount')
    >>> CommercialDiscountRule = Model.get('commercial_discount.rule')
    >>> Company = Model.get('company.company')
    >>> Configuration = Model.get('account.configuration')
    >>> Contract = Model.get('contract')
    >>> ContractPremium = Model.get('contract.premium')
    >>> Country = Model.get('country.country')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
    >>> Insurer = Model.get('insurer')
    >>> ItemDescription = Model.get('offered.item.description')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> Product = Model.get('offered.product')
    >>> RuleEngine = Model.get('rule_engine')
    >>> RuleEngineContext = Model.get('rule_engine.context')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> User = Model.get('res.user')

Constants::

    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 1)

Create or fetchh Currency::

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

Create Fiscal Year::

    >>> fiscalyear = FiscalYear(name='2014')
    >>> fiscalyear.start_date = datetime.date(datetime.date.today().year, 1, 1)
    >>> fiscalyear.end_date = datetime.date(datetime.date.today().year, 12, 31)
    >>> fiscalyear.company = company
    >>> post_move_seq = Sequence(name='2014', code='account.move',
    ...     company=company)
    >>> post_move_seq.save()
    >>> fiscalyear.post_move_sequence = post_move_seq
    >>> seq = SequenceStrict(name='2014',
    ...     code='account.invoice', company=company)
    >>> seq.save()
    >>> bool(fiscalyear.invoice_sequences.pop())
    True
    >>> fiscalyear.save()
    >>> invoice_sequence = InvoiceSequence()
    >>> invoice_sequence.out_invoice_sequence = seq
    >>> invoice_sequence.in_invoice_sequence = seq
    >>> invoice_sequence.out_credit_note_sequence = seq
    >>> invoice_sequence.in_credit_note_sequence = seq
    >>> invoice_sequence.fiscalyear = fiscalyear
    >>> invoice_sequence.company = company
    >>> invoice_sequence.save()
    >>> fiscalyear.reload()
    >>> FiscalYear.create_period([fiscalyear.id], config.context)

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

Create billing modes::

    >>> payment_term = PaymentTerm()
    >>> payment_term.name = 'direct'
    >>> payment_term.lines.append(PaymentTermLine())
    >>> payment_term.save()
    >>> freq_quarterly = BillingMode()
    >>> freq_quarterly.name = 'Quarterly'
    >>> freq_quarterly.code = 'quarterly'
    >>> freq_quarterly.frequency = 'quarterly'
    >>> freq_quarterly.allowed_payment_terms.append(payment_term)
    >>> freq_quarterly.save()

Create billing modes::

    >>> payment_term_y = PaymentTerm()
    >>> payment_term_y.name = 'direct'
    >>> payment_term_y.lines.append(PaymentTermLine())
    >>> payment_term_y.save()
    >>> freq_yearly = BillingMode()
    >>> freq_yearly.name = 'Yearly'
    >>> freq_yearly.code = 'yearly'
    >>> freq_yearly.frequency = 'yearly'
    >>> freq_yearly.allowed_payment_terms.append(payment_term_y)
    >>> freq_yearly.save()

Define tax configuration per line::

    >>> configuration, = Configuration.find([])
    >>> configuration.tax_rounding = 'line'
    >>> configuration.save()

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
    >>> coverage.allow_subscribe_coverage_multiple_times = True
    >>> coverage.save()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.coverages.append(coverage)
    >>> product.billing_rules[-1].billing_modes.append(freq_quarterly)
    >>> product.billing_rules[-1].billing_modes.append(freq_yearly)
    >>> product.save()

Rule context::

    >>> rule_context = RuleEngineContext(1)

Create eligibility rule::

    >>> eligibility_rule = RuleEngine()
    >>> eligibility_rule.algorithm = (
    ...     'age = annees_entre(date_de_naissance_souscripteur(),'
    ...     'date_effet_initiale_contrat())\n'
    ...     'if age < 35:\n'
    ...     '   return True\n'
    ...     'else:\n'
    ...     '   return False')
    >>> eligibility_rule.context = rule_context
    >>> eligibility_rule.name = 'discount eligibility'
    >>> eligibility_rule.rec_name = 'discount eligibility'
    >>> eligibility_rule.result_type = 'boolean'
    >>> eligibility_rule.short_name = 'discount_eligibility'
    >>> eligibility_rule.status = 'validated'
    >>> eligibility_rule.type_ = 'discount_eligibility'
    >>> eligibility_rule.save()

Create duration rules::

    >>> duration_rule1 = RuleEngine()
    >>> duration_rule1.algorithm = ('start_date=date_effet_initiale_contrat()\n'
    ...     'end_date=ajouter_mois(start_date,2,False)\n'
    ...     'end_date=ajouter_jours(end_date, -1)\n'
    ...     'return(start_date,end_date)')
    >>> duration_rule1.context = rule_context
    >>> duration_rule1.name = 'first two months'
    >>> duration_rule1.rec_name = 'first two months'
    >>> duration_rule1.result_type = 'list'
    >>> duration_rule1.short_name = 'first_two_months'
    >>> duration_rule1.status = 'validated'
    >>> duration_rule1.type_ = 'discount_duration'
    >>> duration_rule1.save()
    >>> duration_rule2 = RuleEngine()
    >>> duration_rule2.algorithm = (
    ...     'start_date=ajouter_mois(date_effet_initiale_contrat(),2,False)\n'
    ...     'end_date=ajouter_annees(date_effet_initiale_contrat(),1,False)\n'
    ...     'end_date=ajouter_jours(end_date, -1)\n'
    ...     'return(start_date,end_date)')
    >>> duration_rule2.context = rule_context
    >>> duration_rule2.name = 'first year'
    >>> duration_rule2.rec_name = 'first year'
    >>> duration_rule2.result_type = 'list'
    >>> duration_rule2.short_name = 'first_year'
    >>> duration_rule2.status = 'validated'
    >>> duration_rule2.type_ = 'discount_duration'
    >>> duration_rule2.save()
    >>> duration_rule3 = RuleEngine()
    >>> duration_rule3.algorithm = (
    ...     'start_date=ajouter_annees(date_effet_initiale_contrat(),1,False)\n'
    ...     'end_date=ajouter_annees(date_effet_initiale_contrat(),2,False)\n'
    ...     'end_date=ajouter_jours(end_date, -1)\n'
    ...     'return(start_date,end_date)')
    >>> duration_rule3.context = rule_context
    >>> duration_rule3.name = 'second year'
    >>> duration_rule3.rec_name = 'second year'
    >>> duration_rule3.result_type = 'list'
    >>> duration_rule3.short_name = 'second_year'
    >>> duration_rule3.status = 'validated'
    >>> duration_rule3.type_ = 'discount_duration'
    >>> duration_rule3.save()
    >>> duration_rule4 = RuleEngine()
    >>> duration_rule4.algorithm = (
    ...     'start_date=ajouter_annees(date_effet_initiale_contrat(),2,False)\n'
    ...     'end_date=ajouter_annees(date_effet_initiale_contrat(),3,False)\n'
    ...     'end_date=ajouter_jours(end_date, -1)\n'
    ...     'return(start_date,end_date)')
    >>> duration_rule4.context = rule_context
    >>> duration_rule4.name = 'third year'
    >>> duration_rule4.rec_name = 'third year'
    >>> duration_rule4.result_type = 'list'
    >>> duration_rule4.short_name = 'third_year'
    >>> duration_rule4.status = 'validated'
    >>> duration_rule4.type_ = 'discount_duration'
    >>> duration_rule4.save()

Create commercial discount::

    >>> commercial_discount = CommercialDiscount()
    >>> commercial_discount.code = 'new_members'
    >>> commercial_discount.name = 'new members'
    >>> commercial_discount.rec_name = 'new members'
    >>> commercial_discount.save()

Create commercial discount rules::

    >>> commercial_rule1 = CommercialDiscountRule()
    >>> commercial_rule1.account_for_modification = product_account
    >>> commercial_rule1.automatic = True
    >>> commercial_rule1.commercial_discount = commercial_discount
    >>> commercial_rule1.duration_rule = duration_rule1
    >>> commercial_rule1.eligibility_rule = eligibility_rule
    >>> commercial_rule1.invoice_line_period_behaviour = 'proportion'
    >>> commercial_rule1.rate = Decimal('1.0')
    >>> commercial_rule1.coverages.append(OptionDescription(coverage.id))
    >>> commercial_rule1.save()
    >>> commercial_rule2 = CommercialDiscountRule()
    >>> commercial_rule2.account_for_modification = product_account
    >>> commercial_rule2.automatic = True
    >>> commercial_rule2.commercial_discount = commercial_discount
    >>> commercial_rule2.duration_rule = duration_rule2
    >>> commercial_rule2.eligibility_rule = eligibility_rule
    >>> commercial_rule2.invoice_line_period_behaviour = 'proportion'
    >>> commercial_rule2.rate = Decimal('0.2')
    >>> commercial_rule2.coverages.append(OptionDescription(coverage.id))
    >>> commercial_rule2.save()
    >>> commercial_rule3 = CommercialDiscountRule()
    >>> commercial_rule3.account_for_modification = product_account
    >>> commercial_rule3.automatic = True
    >>> commercial_rule3.commercial_discount = commercial_discount
    >>> commercial_rule3.duration_rule = duration_rule3
    >>> commercial_rule3.eligibility_rule = eligibility_rule
    >>> commercial_rule3.invoice_line_period_behaviour = 'proportion'
    >>> commercial_rule3.rate = Decimal('0.1')
    >>> commercial_rule3.coverages.append(OptionDescription(coverage.id))
    >>> commercial_rule3.save()
    >>> commercial_rule4 = CommercialDiscountRule()
    >>> commercial_rule4.account_for_modification = product_account
    >>> commercial_rule4.automatic = True
    >>> commercial_rule4.commercial_discount = commercial_discount
    >>> commercial_rule4.duration_rule = duration_rule4
    >>> commercial_rule4.eligibility_rule = eligibility_rule
    >>> commercial_rule4.invoice_line_period_behaviour = 'proportion'
    >>> commercial_rule4.rate = Decimal('0.05')
    >>> commercial_rule4.coverages.append(OptionDescription(coverage.id))
    >>> commercial_rule4.save()
    >>> commercial_discount.rules.append(commercial_rule1)
    >>> commercial_discount.rules.append(commercial_rule2)
    >>> commercial_discount.rules.append(commercial_rule3)
    >>> commercial_discount.rules.append(commercial_rule4)
    >>> commercial_discount.save()

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
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> premium_0 = ContractPremium.create([{
    ...             'option': contract.covered_elements[0].options[0].id,
    ...             'start': contract_start_date,
    ...             'amount': Decimal('120'),
    ...             'frequency': 'yearly',
    ...             'account': product_account.id,
    ...             'rated_entity': (coverage.__class__.__name__ + ','
    ...                 + str(coverage.id)),
    ...             }], config.context)
    >>> contract.save()

Create invoices::

    >>> until_date = contract_start_date + relativedelta(years=4)
    >>> generate_invoice = Wizard('contract.do_invoice', models=[contract])
    >>> generate_invoice.form.up_to_date = until_date
    >>> generate_invoice.execute('invoice')
    >>> contract_invoices = contract.invoices
    >>> first_invoice = contract_invoices[-1]
    >>> first_invoice.invoice.total_amount
    Decimal('80.00')
    >>> second_invoice = contract_invoices[-2]
    >>> second_invoice.invoice.total_amount
    Decimal('108.00')
    >>> third_invoice = contract_invoices[-3]
    >>> third_invoice.invoice.total_amount
    Decimal('114.00')
    >>> fourth_invoice = contract_invoices[-4]
    >>> fourth_invoice.invoice.total_amount
    Decimal('120.00')
