============================================
Contract Insurance Invoice Dunning Scenario
============================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, get_company
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
    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install Modules::

    >>> Module = Model.get('ir.module.module')
    >>> contract_dunning_module = Module.find([
    ...         ('name', '=', 'contract_insurance_invoice_dunning')])[0]
    >>> contract_dunning_module.click('install')
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

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

Create dunning procedure::

    >>> Procedure = Model.get('account.dunning.procedure')
    >>> procedure = Procedure(name='Procedure')
    >>> level = procedure.levels.new()
    >>> level.name = 'Reminder'
    >>> level.sequence = 1
    >>> level.days = 30
    >>> level = procedure.levels.new()
    >>> level.name = 'Formal Demand'
    >>> level.sequence = 2
    >>> level.days = 60
    >>> level = procedure.levels.new()
    >>> level.name = 'Suspend contract'
    >>> level.sequence = 2
    >>> level.days = 90
    >>> level.contract_action = 'hold'
    >>> level = procedure.levels.new()
    >>> level.name = 'Terminate contract'
    >>> level.sequence = 3
    >>> level.days = 100
    >>> level.contract_action = 'terminate'
    >>> level.termination_mode = 'at_last_posted_invoice'
    >>> procedure.save()

Create Product::

    >>> product = init_product()
    >>> product = add_quote_number_generator(product)
    >>> product = add_premium_rules(product)
    >>> product = add_invoice_configuration(product, accounts)
    >>> product = add_insurer_to_product(product)
    >>> product.dunning_procedure = procedure
    >>> product.save()

Create Subscriber::

    >>> subscriber = create_party_person()

Create Contract::

    >>> contract_start_date = datetime.date.today()
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
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')

Create first invoice::

    >>> ContractInvoice = Model.get('contract.invoice')
    >>> Contract.first_invoice([contract.id], config.context)
    >>> first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
    >>> first_invoice.invoice.click('post')

Create dunnings at 30 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=30)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning, = Dunning.find([])
    >>> dunning.contract == contract
    True
    >>> dunning.procedure == procedure
    True

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'done'
    True
    >>> contract.dunning_status
    u'Reminder'
    >>> dunning_contracts = Contract.find([('dunning_status', '=', 'Reminder')])
    >>> len(dunning_contracts)
    1

Create dunnings at 60 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=60)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning, = Dunning.find(['state', '=', 'draft'])

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'done'
    True

Create dunnings at 90 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=90)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning, = Dunning.find(['state', '=', 'draft'])

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'done'
    True
    >>> contract.status == 'hold'
    True

Create dunnings at 100 days::

    >>> create_dunning = Wizard('account.dunning.create')
    >>> create_dunning.form.date = contract_start_date + relativedelta(days=100)
    >>> create_dunning.execute('create_')
    >>> Dunning = Model.get('account.dunning')
    >>> dunning, = Dunning.find(['state', '=', 'draft'])

Process dunnning::

    >>> Wizard('account.dunning.process', [dunning]).execute('process')
    >>> dunning.reload()
    >>> dunning.state == 'done'
    True
    >>> contract.end_date == first_invoice.end
    True
