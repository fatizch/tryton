=========================================
Contract Start Date Endorsement Scenario
=========================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.account.tests.tools import get_accounts, create_chart
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.coog_core.test_framework import execute_test_case

Install Modules::

    >>> config = activate_modules(['analytic_coog', 'contract_insurance_invoice',
    ...     'contract_insurance', 'analytic_contract', 'endorsement'])

Get Models::

    >>> Country = Model.get('country.country')
    >>> Account = Model.get('account.account')
    >>> AccountInvoice = Model.get('account.invoice')
    >>> AccountKind = Model.get('account.account.type')
    >>> FiscalYear = Model.get('account.fiscalyear')
    >>> InvoiceSequence = Model.get('account.fiscalyear.invoice_sequence')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> PaymentTermLine = Model.get('account.invoice.payment_term.line')
    >>> BillingMode = Model.get('offered.billing_mode')
    >>> Product = Model.get('offered.product')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> ExtraData = Model.get('extra_data')
    >>> ProductCategory = Model.get('product.category')
    >>> Uom = Model.get('product.uom')
    >>> AccountProduct = Model.get('product.product')
    >>> Template = Model.get('product.template')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> Contract = Model.get('contract')
    >>> ContractInvoice = Model.get('contract.invoice')
    >>> ContractPremium = Model.get('contract.premium')
    >>> Option = Model.get('contract.option')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> Journal = Model.get('account.journal')
    >>> AnalyticAccountEntry = Model.get('analytic.account.entry')
    >>> AnalyticAccount = Model.get('analytic_account.account')
    >>> ContractOption = Model.get('contract.option')
    >>> AnalyticAccountRule = Model.get('analytic_account.rule')

Constants::

    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)

Create or fetch Currency::

    >>> currency = get_currency(code='EUR')

Create or fetch Country::

    >>> countries = Country.find([('code', '=', 'FR')])
    >>> if not countries:
    ...     country = Country(name='France', code='FR')
    ...     country.save()

Create Company::

    >>> _ = create_company(currency=currency)

Switch user::

    >>> execute_test_case('authorizations_test_case')
    >>> company = get_company()

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
    >>> _ = create_chart(company)

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

Create Test ExtraData::

    >>> extra_data1 = ExtraData()
    >>> extra_data1.name = 'formula'
    >>> extra_data1.type_ = 'selection'
    >>> extra_data1.string = 'formula'
    >>> extra_data1.kind = 'contract'
    >>> extra_data1.selection = 'formula1: Formula1\nformula2:Formula2\n' \
    ...     'formula3:Formula3'
    >>> extra_data1.save()
    >>> extra_data2 = ExtraData()
    >>> extra_data2.name = 'deductible'
    >>> extra_data2.type_ = 'selection'
    >>> extra_data2.string = 'deductible'
    >>> extra_data2.kind = 'contract'
    >>> extra_data2.selection = 'days10: 10\ndays20: 20'
    >>> extra_data2.save()

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
    >>> receivable_account.reconcile = True
    >>> receivable_account.company = company
    >>> receivable_account.party_required = True
    >>> receivable_account.save()
    >>> payable_account = Account()
    >>> payable_account.name = 'Account Payable'
    >>> payable_account.code = 'account_payable'
    >>> payable_account.type = payable_account_kind
    >>> payable_account.company = company
    >>> payable_account.party_required = True
    >>> payable_account.save()

Create billing modes::

    >>> payment_term = PaymentTerm()
    >>> payment_term.name = 'direct'
    >>> payment_term.lines.append(PaymentTermLine())
    >>> payment_term.save()
    >>> freq_monthly = BillingMode()
    >>> freq_monthly.name = 'Monthly'
    >>> freq_monthly.code = 'monthly'
    >>> freq_monthly.frequency = 'monthly'
    >>> freq_monthly.allowed_payment_terms.append(payment_term)
    >>> freq_monthly.save()
    >>> freq_yearly = BillingMode()
    >>> freq_yearly.name = 'Yearly'
    >>> freq_yearly.code = 'yearly'
    >>> freq_yearly.frequency = 'yearly'
    >>> freq_yearly.allowed_payment_terms.append(PaymentTerm.find([])[0])
    >>> freq_yearly.save()

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
    >>> product_account, = Account.find([('code', '=', 'product_account')])
    >>> coverage.account_for_billing = product_account
    >>> coverage.save()
    >>> accounts = get_accounts(company)

Create Contract Fee::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.code = 'account_category_1'
    >>> account_category.save()
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> template = Template()
    >>> template.name = 'contract Fee Template'
    >>> template.default_uom = unit
    >>> template.account_category = account_category
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.products[0].code = 'contract Fee product'
    >>> template.save()
    >>> fee_product = template.products[0]
    >>> Fee = Model.get('account.fee')
    >>> contract_fee = Fee()
    >>> contract_fee.name = 'contract Fee'
    >>> contract_fee.code = 'contract_fee'
    >>> contract_fee.frequency = 'at_contract_signature'
    >>> contract_fee.type = 'fixed'
    >>> contract_fee.amount = Decimal('800.0')
    >>> contract_fee.product = fee_product
    >>> contract_fee.save()
    >>> product = Product()
    >>> product.company = company
    >>> product.currency = currency
    >>> product.name = 'Test Product'
    >>> product.code = 'test_product'
    >>> product.contract_generator = contract_sequence
    >>> product.quote_number_sequence = quote_sequence
    >>> product.start_date = product_start_date
    >>> product.coverages.append(coverage)
    >>> product.fees.append(contract_fee)
    >>> product.billing_rules[-1].billing_modes.append(freq_monthly)
    >>> product.billing_rules[-1].billing_modes.append(freq_yearly)
    >>> product.extra_data_def.append(extra_data1)
    >>> product.extra_data_def.append(extra_data2)
    >>> product.save()
    >>> product = Model.get('offered.product')(product.id)
    >>> company = get_company()

Create Subscriber::

    >>> subscriber = Party()
    >>> subscriber.name = 'Doe'
    >>> subscriber.first_name = 'John'
    >>> subscriber.is_person = True
    >>> subscriber.gender = 'male'
    >>> subscriber.account_receivable = Account(receivable_account.id)
    >>> subscriber.account_payable = Account(payable_account.id)
    >>> subscriber.birth_date = datetime.date(1980, 10, 14)
    >>> subscriber.save()

Create Test Contract::

    >>> freq_yearly = BillingMode(freq_yearly.id)
    >>> payment_term = PaymentTerm(payment_term.id)
    >>> root = AnalyticAccount()
    >>> root.code = 'test'
    >>> root.name = 'Test'
    >>> root.type = 'root'
    >>> root.company = company
    >>> root.save()
    >>> account = AnalyticAccount()
    >>> account.code = 'analytic_child'
    >>> account.name = 'Analytic child'
    >>> account.type = 'normal'
    >>> account.root = root
    >>> account.company = company
    >>> account.parent = root
    >>> account.save()
    >>> account2 = AnalyticAccount()
    >>> account2.code = 'second_count'
    >>> account2.name = 'Second Count'
    >>> account2.type = 'normal'
    >>> account2.root = root
    >>> account2.company = company
    >>> account2.parent = root
    >>> account2.save()
    >>> analytic_account_rule1 = AnalyticAccountRule()
    >>> analytic_account_rule1.code = 'test_account_rule'
    >>> analytic_account_rule1.extra_data = {'formula': 'formula1'}
    >>> analytic_account_rule1.journal, = Journal.find(['type', '=', 'revenue'])
    >>> analytic_account_rule1.account = product_account
    >>> analytic_account_rule1.analytic_accounts[0].account = account
    >>> analytic_account_rule1.company = company
    >>> analytic_account_rule1.save()
    >>> analytic_account_rule2 = AnalyticAccountRule()
    >>> analytic_account_rule2.code = 'test_account_rule2'
    >>> analytic_account_rule2.extra_data = {'formula': 'formula2'}
    >>> analytic_account_rule2.journal, = Journal.find(['type', '=', 'revenue'])
    >>> analytic_account_rule2.account = product_account
    >>> analytic_account_rule2.analytic_accounts[0].account = account2
    >>> analytic_account_rule2.company = company
    >>> analytic_account_rule2.save()
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.status = 'quote'
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=freq_yearly, payment_term=payment_term))
    >>> contract.save()
    >>> product_account, = Account.find([('code', '=', 'product_account')])
    >>> coverage = OptionDescription(coverage.id)
    >>> Wizard('contract.activate', models=[contract]).execute('apply')
    >>> option = ContractOption(contract.options[0].id)
    >>> option.premiums.append(ContractPremium(start=contract_start_date,
    ...         amount=Decimal('100'), frequency='once_per_contract',
    ...         account=product_account, rated_entity=coverage))
    >>> option.save()
    >>> contract.premiums.append(ContractPremium(start=contract_start_date,
    ...         amount=Decimal('15'), frequency='monthly', account=product_account,
    ...         rated_entity=product))
    >>> contract.premiums.append(ContractPremium(
    ...         start=contract_start_date + datetime.timedelta(days=40),
    ...         amount=Decimal('20'), frequency='yearly', account=product_account,
    ...         rated_entity=coverage))
    >>> contract.extra_datas[0].extra_data_values = {'formula': 'formula1',
    ...     'deductible': '10 days'}
    >>> contract.save()
    >>> Contract.first_invoice([contract.id], config.context)
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]),
    ...     key=lambda x: x.invoice.start)
    >>> AccountInvoice.post([all_invoices[0].invoice.id], config.context)
    >>> all_invoices[0].invoice.state
    'posted'
    >>> for line in all_invoices[0].invoice.move.lines:
    ...     if line.account == product_account:
    ...         assert len(line.analytic_lines) == 1
    ...         assert line.analytic_lines[0].account == account
    ...         assert line.debit == line.analytic_lines[0].debit
    ...         assert line.credit == line.analytic_lines[0].credit
    ...     else:
    ...         assert len(line.analytic_lines) == 0
    >>> all_invoices[0].invoice.click('cancel')
    >>> for line in all_invoices[0].invoice.cancel_move.lines:
    ...     if line.account == product_account:
    ...         assert len(line.analytic_lines) == 1
    ...         assert line.analytic_lines[0].account == account
    ...         assert line.debit == line.analytic_lines[0].credit
    ...         assert line.credit == -line.analytic_lines[0].debit
    ...     else:
    ...         assert len(line.analytic_lines) == 0
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
    >>> change_extra_data.save()
    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = change_extra_data
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = subscriber
    >>> new_endorsement.form.effective_date = datetime.date(2014, 5, 20)
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.form.new_extra_data = {'formula': 'formula2'}
    >>> new_endorsement.execute('change_contract_extra_data_next')
    >>> new_endorsement.execute('apply_endorsement')
    >>> contract.save()
    >>> Contract.first_invoice([contract.id], config.context)
    >>> all_invoices = sorted(ContractInvoice.find([('contract', '=', contract.id),
    ...             ('invoice.state', '=', 'validated')]),
    ...     key=lambda x: x.invoice.start)
    >>> AccountInvoice.post([all_invoices[0].invoice.id, all_invoices[1].invoice.id],
    ...     config.context)
    >>> all_invoices[1].invoice.state
    'posted'
    >>> for line in all_invoices[1].invoice.move.lines:
    ...     if line.account == product_account:
    ...         assert len(line.analytic_lines) == 1
    ...         assert line.analytic_lines[0].account == account2
    ...         assert line.debit == line.analytic_lines[0].debit
    ...         assert line.credit == line.analytic_lines[0].credit
    ...     else:
    ...         assert len(line.analytic_lines) == 0
    >>> all_invoices[0].invoice.state
    'posted'
    >>> for line in all_invoices[0].invoice.move.lines:
    ...     if line.account == product_account:
    ...         assert len(line.analytic_lines) == 1
    ...         if line.origin.coverage_start == datetime.date(2014, 4, 10):
    ...             assert line.analytic_lines[0].account == account
    ...         if line.origin.coverage_start == datetime.date(2014, 5, 20):
    ...             assert line.analytic_lines[0].account == account2
    ...         assert line.debit == line.analytic_lines[0].debit
    ...         assert line.credit == line.analytic_lines[0].credit
    ...     else:
    ...         assert len(line.analytic_lines) == 0
