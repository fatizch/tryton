==============================
Commission Insurance Scenario
==============================

Imports::

    >>> import datetime
    >>> from proteus import Model, Wizard
    >>> from decimal import Decimal
    >>> from trytond.tests.tools import activate_modules
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

    >>> config = activate_modules('commission_insurer')

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

Create Fiscal Year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create Waiting Insurer Account::

    >>> AccountKind = Model.get('account.account.type')
    >>> waiting_account_kind = AccountKind()
    >>> waiting_account_kind.name = 'Waiting Account Insurer Kind'
    >>> waiting_account_kind.company = company
    >>> waiting_account_kind.save()
    >>> Account = Model.get('account.account')
    >>> company_waiting_account = Account()
    >>> company_waiting_account.name = 'Company Waiting Account'
    >>> company_waiting_account.code = 'company_wiating_account'
    >>> company_waiting_account.kind = 'revenue'
    >>> company_waiting_account.party_required = True
    >>> company_waiting_account.type = waiting_account_kind
    >>> company_waiting_account.company = company
    >>> company_waiting_account.save()

Create Product::

    >>> product = init_product()
    >>> product = add_quote_number_generator(product)
    >>> product = add_premium_rules(product)
    >>> product = add_invoice_configuration(product, accounts)
    >>> for coverage in product.coverages:
    ...     coverage.account_for_billing = company_waiting_account
    >>> product = add_insurer_to_product(product)
    >>> product.save()
    >>> expense = accounts['expense']
    >>> revenue = accounts['revenue']
    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category Waiting")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.code = 'account_category'
    >>> account_category.save()

Create commission product::

    >>> Product = Model.get('product.product')
    >>> Template = Model.get('product.template')
    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> commission_product = Product()
    >>> template = Template()
    >>> template.name = 'Commission'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.account_category = account_category
    >>> template.products[0].code = 'commission_product'
    >>> template.save()
    >>> commission_product = template.products[0]

Create insurer commission plan::

    >>> Coverage = Model.get('offered.option.description')
    >>> Plan = Model.get('commission.plan')
    >>> insurer_plan = Plan(name='Insurer Plan')
    >>> insurer_plan.commission_product = commission_product
    >>> insurer_plan.commission_method = 'payment'
    >>> insurer_plan.type_ = 'principal'
    >>> coverage = product.coverages[0].id
    >>> line = insurer_plan.lines.new()
    >>> line.options.append(Coverage(coverage))
    >>> line.formula = 'amount * 0.6'
    >>> insurer_plan.save()

Create insurer agent::

    >>> Agent = Model.get('commission.agent')
    >>> Insurer = Model.get('insurer')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> insurer, = Insurer.find([])
    >>> insurer.party.supplier_payment_term, = PaymentTerm.find([])
    >>> insurer.party.save()
    >>> insurer.save()
    >>> agent = Agent(party=insurer.party)
    >>> agent.type_ = 'principal'
    >>> agent.plan = insurer_plan
    >>> agent.currency = company.currency
    >>> agent.insurer = insurer
    >>> agent.save()

Create broker commission plan::

    >>> Coverage = Model.get('offered.option.description')
    >>> Plan = Model.get('commission.plan')
    >>> broker_plan = Plan(name='Broker Plan')
    >>> broker_plan.commission_product = commission_product
    >>> broker_plan.commission_method = 'payment'
    >>> broker_plan.type_ = 'agent'
    >>> coverage = product.coverages[0].id
    >>> line = broker_plan.lines.new()
    >>> line.options.append(Coverage(coverage))
    >>> line.formula = 'amount * 0.2'
    >>> broker_plan.save()

Create broker and broker agent::

    >>> Agent = Model.get('commission.agent')
    >>> Insurer = Model.get('insurer')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> Party = Model.get('party.party')
    >>> DistributionNetwork = Model.get('distribution.network')
    >>> broker_party = Party(name='Broker')
    >>> broker_party.supplier_payment_term, = PaymentTerm.find([])
    >>> broker_party.save()
    >>> broker = DistributionNetwork(name='Broker', code='broker', party=broker_party,
    ...     is_broker=True)
    >>> broker.save()
    >>> broker_agent = Agent(party=broker_party)
    >>> broker_agent.type_ = 'agent'
    >>> broker_agent.plan = broker_plan
    >>> broker_agent.currency = company.currency
    >>> broker_agent.save()

Create Subscriber::

    >>> subscriber = create_party_person()

Create Test Contract::

    >>> contract_start_date = datetime.date.today()
    >>> Contract = Model.get('contract')
    >>> ContractPremium = Model.get('contract.premium')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> contract = Contract()
    >>> contract.contract_number = '123456789'
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=product.billing_modes[0],
    ...         payment_term=product.billing_modes[0].allowed_payment_terms[0]))
    >>> contract.dist_network = DistributionNetwork(broker.id)
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')

Create invoice::

    >>> ContractInvoice = Model.get('contract.invoice')
    >>> Contract.first_invoice([contract.id], config.context)
    >>> first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
    >>> first_invoice.invoice.total_amount == Decimal('100')
    True

Post Invoice::

    >>> first_invoice.invoice.click('post')
    >>> line = first_invoice.invoice.lines[0]
    >>> len(line.commissions)
    1
    >>> set([(x.amount, x.agent.party.name) for x in line.commissions]) == set([
    ...     (Decimal('60'), 'Insurer')])
    True

Pay invoice::

    >>> Account = Model.get('account.account')
    >>> Journal = Model.get('account.journal')
    >>> cash_journal, = Journal.find([('type', '=', 'cash')])
    >>> account_cash = accounts['cash']
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = cash_journal
    >>> payment_method.credit_account = account_cash
    >>> payment_method.debit_account = account_cash
    >>> payment_method.save()
    >>> pay = Wizard('account.invoice.pay', [first_invoice.invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.execute('choice')

Create insurer commission invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> create_invoice = Wizard('account.invoice.create.insurer_slip')
    >>> create_invoice.form.insurers.append(agent.party)
    >>> create_invoice.form.until_date = None
    >>> create_invoice.form.notice_kind = 'options'
    >>> create_invoice.execute('create_')
    >>> invoice, = Invoice.find([('type', '=', 'in')])
    >>> assert invoice.total_amount == Decimal('40'), 'Expected base invoice amount ' \
    ...     'to be 40.0, got %.2f' % invoice.total_amount

Cancel commission invoice::

    >>> invoice.click('cancel')
    >>> invoice.reload()
    >>> MoveLine = Model.get('account.move.line')
    >>> MoveLine.find([('principal_invoice_line', 'in', [x.id for x in invoice.lines])])
    []

Recreate insurer commission invoice::

    >>> agent.reload()
    >>> Invoice = Model.get('account.invoice')
    >>> create_invoice = Wizard('account.invoice.create.insurer_slip')
    >>> create_invoice.form.insurers.append(agent.party)
    >>> create_invoice.form.until_date = None
    >>> create_invoice.form.notice_kind = 'options'
    >>> create_invoice.execute('create_')
    >>> invoice, = Invoice.find([('type', '=', 'in'),
    ...         ('state', '!=', 'cancel')])
    >>> assert invoice.total_amount == Decimal('40'), 'Expected re-generated invoice' \
    ...     ' amount to be 40.0, got %.2f' % invoice.total_amount
    >>> invoice.click('post')

Cancel Invoice::

    >>> Contract.first_invoice([contract.id], config.context)
    >>> first_invoice.invoice.state
    'cancel'

Create commission invoice::

    >>> agent.reload()
    >>> Invoice = Model.get('account.invoice')
    >>> create_invoice = Wizard('account.invoice.create.insurer_slip')
    >>> create_invoice.form.insurers.append(agent.party)
    >>> create_invoice.form.until_date = None
    >>> create_invoice.form.notice_kind = 'options'
    >>> create_invoice.execute('create_')
    >>> invoice = Invoice.find([('type', '=', 'in'),
    ...         ('state', '!=', 'cancel')])[0]
    >>> assert invoice.total_amount == Decimal('-40'), 'Expected cancelled invoice ' \
    ...     'amount to be -40.0, got %.2f' % invoice.total_amount
