===============================
Contract Subscription Scenario
===============================

Imports::

    >>> from proteus import config, Model, Wizard

Constants::

    >>> NEEDED_MODULES = [
    ...     'account_payment_cog',
    ...     'loan',
    ...     'billing_group_life_fr',
    ...     'party_cog',
    ...     'contract_life_process',
    ...     'contract_insurance',
    ...     'endorsement',
    ...     'contract_insurance_health_fr',
    ...     'commission',
    ...     'company_cog',
    ...     'distribution',
    ...     'account_payment_sepa_cog',
    ...     'claim_life_process',
    ...     'collection_insurance',
    ...     'claim_process',
    ...     'billing_individual',
    ...     'contract_insurance_process',
    ...     'currency_cog',
    ...     'cog_utils',
    ...     'cog_translation',
    ...     'collection',
    ...     'bank_cog',
    ...     'commission_group',
    ...     'contract_group_process',
    ...     'task_manager',
    ...     'rule_engine',
    ...     'contract_life',
    ...     'offered_distribution',
    ...     'offered',
    ...     'contract',
    ...     'table',
    ...     'offered_property_casualty',
    ...     'country_cog',
    ...     'claim_life',
    ...     'contract_cash_value',
    ...     'process',
    ...     'contract_group',
    ...     'offered_insurance',
    ...     'account_payment',
    ...     'offered_life',
    ...     'health',
    ...     'process_cog',
    ...     'offered_cash_value',
    ...     'bank_fr',
    ...     'claim_credit',
    ...     'party_fr',
    ...     'claim',
    ...     'billing',
    ...     'account_cog',
    ...     ]

Create Database::

    >>> config = config.set_trytond(database_type='sqlite')
    >>> config.pool.test = True
    >>> Module = Model.get('ir.module.module')
    >>> coop_utils_modules = Module.find([('name', 'in', NEEDED_MODULES)])
    >>> for module in coop_utils_modules:
    ...     Module.install([module.id], config.context)
    >>> Wizard('ir.module.module.install_upgrade').execute('upgrade')

Import Exported DB::

    >>> wizard = Wizard('ir.test_case.run')
    >>> wizard.form.select_all_test_cases = True
    >>> wizard.form.select_all_files = True
    >>> wizard.execute('execute_test_cases')
    >>> wizard.execute('end')
    >>> Product = Model.get('offered.product')
    >>> len(Product.find([], order=[('code', 'ASC')]))
    9
