=============================
Endorsement Renewal Scenario
=============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import config, Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.offered.tests.tools import init_product
    >>> from trytond.modules.party_cog.tests.tools import create_party_person
    >>> from trytond.modules.contract.tests.tools import add_quote_number_generator
    >>> from trytond.modules.country_cog.tests.tools import create_country

Create Database::


Install Modules::

    >>> config = activate_modules('endorsement_renewal')

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

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create Product::

    >>> product = init_product()
    >>> product = add_quote_number_generator(product)
    >>> renewal_rule = product.term_renewal_rule.new()
    >>> renewal_rule.allow_renewal = True
    >>> Rule = Model.get('rule_engine')
    >>> subscription_date_sync_rule, = Rule.find([
    ...         ('short_name', '=', 'product_term_renewal_sync_sub_date')])
    >>> renewal_rule.rule = subscription_date_sync_rule
    >>> renewal_rule.product = product
    >>> product.save()

Create Subscriber::

    >>> subscriber = create_party_person()

Create Change Start Date Endorsement::

    >>> Endorsement = Model.get('endorsement')
    >>> EndorsementContract = Model.get('endorsement.contract')
    >>> EndorsementDefinition = Model.get('endorsement.definition')
    >>> EndorsementDefinitionPartRelation = Model.get(
    ...     'endorsement.definition-endorsement.part')
    >>> EndorsementPart = Model.get('endorsement.part')
    >>> renew_contract_part = EndorsementPart()
    >>> renew_contract_part.name = 'Renew Contract'
    >>> renew_contract_part.code = 'renew_contract'
    >>> renew_contract_part.kind = 'contract'
    >>> renew_contract_part.view = 'renew_contract'
    >>> renew_contract_part.save()
    >>> renew_contract = EndorsementDefinition()
    >>> renew_contract.name = 'Renew Contract'
    >>> renew_contract.code = 'renew_contract'
    >>> renew_contract.ordered_endorsement_parts.append(
    ...     EndorsementDefinitionPartRelation(endorsement_part=renew_contract_part))
    >>> renew_contract.save()

Constants::

    >>> today = datetime.date.today()
    >>> product_start_date = datetime.date(2014, 1, 1)
    >>> contract_start_date = datetime.date(2014, 4, 10)
    >>> endorsement_effective_date = datetime.date(2014, 10, 21)

Create Test Contract::

    >>> Contract = Model.get('contract')
    >>> contract = Contract()
    >>> contract.company = company
    >>> contract.subscriber = subscriber
    >>> contract.start_date = contract_start_date
    >>> contract.product = product
    >>> contract.contract_number = '123456789'
    >>> contract.save()
    >>> Wizard('contract.activate', models=[contract]).execute('apply')

Start Testing::

    >>> len(contract.activation_history) == 1
    True
    >>> contract.start_date == contract_start_date
    True
    >>> contract.end_date == contract_start_date + relativedelta(years=1, days=-1)
    True

New Endorsement::

    >>> new_endorsement = Wizard('endorsement.start')
    >>> new_endorsement.form.contract = contract
    >>> new_endorsement.form.endorsement_definition = renew_contract
    >>> new_endorsement.form.endorsement = None
    >>> new_endorsement.form.applicant = None
    >>> new_endorsement.form.effective_date = contract.end_date
    >>> new_endorsement.execute('start_endorsement')
    >>> new_endorsement.execute('renew_contract_next')
    >>> new_endorsement.execute('apply_endorsement')
    >>> contract.save()

Start Testing::

    >>> len(contract.activation_history) == 2
    True
    >>> contract.activation_history[1].start_date == contract_start_date + \
    ...     relativedelta(years=1)
    True
    >>> contract.activation_history[1].end_date == contract_start_date + \
    ...     relativedelta(years=2, days=-1)
    True
