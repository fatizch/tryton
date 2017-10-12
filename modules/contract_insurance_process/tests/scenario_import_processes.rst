==========================
Import Processes Scenario
==========================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.process_cog.tests.tools import test_import_processes
    >>> from trytond.tests.tools import activate_modules

Install Modules::

    >>> config = activate_modules(['contract_insurance_process',
    ...         'contract_insurance_invoice', 'contract_loan_invoice'])
    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)
    >>> test_import_processes()
