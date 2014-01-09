===============================
Contract Subscription Scenario
===============================

Imports::

    >>> from proteus import config, Model, Wizard

Constants::

    >>> NEEDED_MODULES = [
    ...     'coop_account_payment',
    ...     'loan',
    ...     'life_billing_collective_fr',
    ...     'coop_party',
    ...     'life_contract_subscription',
    ...     'insurance_contract',
    ...     'endorsement',
    ...     'health_fr',
    ...     'commission',
    ...     'coop_company',
    ...     'distribution',
    ...     'coop_account_payment_sepa',
    ...     'life_claim_process',
    ...     'insurance_collection',
    ...     'claim_process',
    ...     'billing_individual',
    ...     'insurance_contract_subscription',
    ...     'coop_currency',
    ...     'coop_utils',
    ...     'coop_translation',
    ...     'collection',
    ...     'coop_bank',
    ...     'commission_collective',
    ...     'insurance_collective_subscription',
    ...     'task_manager',
    ...     'rule_engine',
    ...     'life_contract',
    ...     'distribution_product',
    ...     'offered',
    ...     'contract',
    ...     'table',
    ...     'property_product',
    ...     'coop_country',
    ...     'life_claim',
    ...     'cash_value_contract',
    ...     'process',
    ...     'insurance_collective',
    ...     'insurance_product',
    ...     'account_payment',
    ...     'life_product',
    ...     'health',
    ...     'coop_process',
    ...     'cash_value_product',
    ...     'bank_fr',
    ...     'loan_claim',
    ...     'coop_party_fr',
    ...     'claim',
    ...     'billing',
    ...     'coop_account',
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
