==============================
Commission Insurance Scenario
==============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
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

    >>> config = activate_modules('commission_insurance_recovery')

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

Create Broker Fee Account::

    >>> AccountKind = Model.get('account.account.type')
    >>> broker_fee_kind = AccountKind()
    >>> broker_fee_kind.name = 'Broker Fee Account Kind'
    >>> broker_fee_kind.company = company
    >>> broker_fee_kind.save()
    >>> Account = Model.get('account.account')
    >>> broker_fee_account = Account()
    >>> broker_fee_account.name = 'Broker Fee Account'
    >>> broker_fee_account.code = 'broker_fee_account'
    >>> broker_fee_account.kind = 'other'
    >>> broker_fee_account.party_required = True
    >>> broker_fee_account.type = broker_fee_kind
    >>> broker_fee_account.company = company
    >>> broker_fee_account.save()

Create Broker Fee::

    >>> Product = Model.get('product.product')
    >>> Template = Model.get('product.template')
    >>> template = Template()
    >>> template.name = 'Broker Fee Template'
    >>> template.account_expense = broker_fee_account
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.products[0].code = 'broker_fee_product'
    >>> template.save()
    >>> product = template.products[0]
    >>> Fee = Model.get('account.fee')
    >>> broker_fee = Fee()
    >>> broker_fee.name = 'Broker Fee'
    >>> broker_fee.code = 'broker_fee'
    >>> broker_fee.frequency = 'once_per_contract'
    >>> broker_fee.type = 'fixed'
    >>> broker_fee.amount = Decimal('20.0')
    >>> broker_fee.product = product
    >>> broker_fee.broker_fee = True
    >>> broker_fee.save()

Create Product::

    >>> product = init_product()
    >>> product = add_quote_number_generator(product)
    >>> product = add_premium_rules(product)
    >>> product = add_invoice_configuration(product, accounts)
    >>> product = add_insurer_to_product(product)
    >>> product.fees.append(broker_fee)
    >>> product.save()

Create commission product::

    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> commission_product = Product()
    >>> template = Template()
    >>> template.name = 'Commission'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.account_expense = accounts['expense']
    >>> template.account_revenue = accounts['revenue']
    >>> template.products[0].code = 'commission_product'
    >>> template.save()
    >>> commission_product = template.products[0]

Create recovery rule::

    >>> Rule = Model.get('rule_engine')
    >>> RuleContext = Model.get('rule_engine.context')
    >>> recovery_rule = Rule()
    >>> recovery_rule.name = 'Recovery Rule'
    >>> recovery_rule.short_name = 'recovery_rule'
    >>> recovery_rule.algorithm = 'return somme_commissions_pour_option() / 2.0'
    >>> recovery_rule.status = 'validated'
    >>> recovery_rule.type_ = 'commission'
    >>> recovery_rule.context, = RuleContext.find(
    ...     [('name', '=', 'Commission Context')])
    >>> recovery_rule.save()
    >>> Recovery = Model.get('commission.plan.recovery_rule')
    >>> recovery = Recovery()
    >>> recovery.name = 'Recovery rule based on 24 month'
    >>> recovery.code = 'Recovery rule based on 24 month'
    >>> recovery.rule = recovery_rule
    >>> recovery.save()

Create broker commission plan::

    >>> Plan = Model.get('commission.plan')
    >>> Coverage = Model.get('offered.option.description')
    >>> broker_plan = Plan(name='Broker Plan')
    >>> broker_plan.commission_product = commission_product
    >>> broker_plan.commission_method = 'payment'
    >>> broker_plan.type_ = 'agent'
    >>> broker_plan.commission_recovery = recovery
    >>> line = broker_plan.lines.new()
    >>> coverage = product.coverages[0].id
    >>> line.options.append(Coverage(coverage))
    >>> line.use_rule_engine = True
    >>> rule, = Rule.find([('short_name', '=', 'commission_lineaire')])
    >>> line.rule_extra_data = {}
    >>> line.rule = rule
    >>> line.rule_extra_data = {'pourcentage_commission': 10}
    >>> broker_plan.save()

Create insurer commission plan::

    >>> Plan = Model.get('commission.plan')
    >>> insurer_plan = Plan(name='Insurer Plan')
    >>> insurer_plan.commission_product = commission_product
    >>> insurer_plan.commission_method = 'payment'
    >>> insurer_plan.type_ = 'principal'
    >>> insurer_plan.commission_recovery = recovery
    >>> coverage = product.coverages[0].id
    >>> line = insurer_plan.lines.new()
    >>> line.options.append(Coverage(coverage))
    >>> line.formula = 'amount * 0.6'
    >>> insurer_plan.save()

Create broker agent::

    >>> Agent = Model.get('commission.agent')
    >>> Party = Model.get('party.party')
    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> broker_party = Party(name='Broker')
    >>> broker_party.supplier_payment_term, = PaymentTerm.find([])
    >>> broker_party.save()
    >>> DistributionNetwork = Model.get('distribution.network')
    >>> broker = DistributionNetwork(name='Broker', code='broker', party=broker_party,
    ...     is_broker=True)
    >>> broker.save()
    >>> agent_broker = Agent(party=broker_party)
    >>> agent_broker.type_ = 'agent'
    >>> agent_broker.plan = broker_plan
    >>> agent_broker.currency = company.currency
    >>> agent_broker.save()

Create insurer agent::

    >>> Insurer = Model.get('insurer')
    >>> insurer, = Insurer.find([])
    >>> agent = Agent(party=insurer.party)
    >>> agent.type_ = 'principal'
    >>> agent.plan = insurer_plan
    >>> agent.currency = company.currency
    >>> agent.save()

Create Subscriber::

    >>> subscriber = create_party_person()

Create Test Contract::

    >>> contract_start_date = datetime.date(datetime.date.today().year, 1, 1)
    >>> Contract = Model.get('contract')
    >>> ContractPremium = Model.get('contract.premium')
    >>> BillingInformation = Model.get('contract.billing_information')
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.billing_informations.append(BillingInformation(date=None,
    ...         billing_mode=product.billing_modes[0],
    ...         payment_term=product.billing_modes[0].allowed_payment_terms[0]))
    >>> contract.contract_number = '123456789'
    >>> contract.dist_network = DistributionNetwork(broker.id)
    >>> contract.agent = agent_broker
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')

Create invoices::

    >>> ContractInvoice = Model.get('contract.invoice')
    >>> until_date = contract_start_date + relativedelta(months=6)
    >>> generate_invoice = Wizard('contract.do_invoice', models=[contract])
    >>> generate_invoice.form.up_to_date = until_date
    >>> generate_invoice.execute('invoice')
    >>> contract_invoices = contract.invoices
    >>> first_invoice = contract_invoices[-1]
    >>> first_invoice.invoice.total_amount
    Decimal('120.00')

Post Invoices::

    >>> for contract_invoice in contract_invoices[::-1]:
    ...     contract_invoice.invoice.click('post')

Terminate Contract::

    >>> end_date = contract_start_date + relativedelta(months=5, days=-1)
    >>> config._context['client_defined_date'] = end_date + relativedelta(days=1)
    >>> SubStatus = Model.get('contract.sub_status')
    >>> sub_status = SubStatus()
    >>> sub_status.name = 'Client termination'
    >>> sub_status.code = 'client_termination'
    >>> sub_status.status = 'terminated'
    >>> sub_status.save()
    >>> end_contract = Wizard('contract.stop', models=[contract])
    >>> end_contract.form.status = 'terminated'
    >>> end_contract.form.at_date = end_date
    >>> end_contract.form.sub_status = sub_status
    >>> end_contract.execute('stop')

Check commissions (example: broker: 10% x 100 x 5 months / 2 )::

    >>> Commission = Model.get('commission')
    >>> recovery_commissions = Commission.find([('is_recovery', '=', True)])
    >>> len(recovery_commissions)
    2
    >>> [(c.amount, c.agent.id) for c in recovery_commissions] == [(-25, 1), (-150, 2)]
    True

Reactivate Contract::

    >>> Wizard('contract.reactivate', models=[contract]).execute('reactivate')
    >>> recovery_commissions = Commission.find([('is_recovery', '=', True)])
    >>> len(recovery_commissions)
    0
