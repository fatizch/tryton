==========================
Import Processes Scenario
==========================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.process_cog.tests.tools import test_import_processes
    >>> from trytond.tests.tools import activate_modules

Install Modules::

    >>> config = activate_modules(['claim_life_process', 'claim_salary_fr',
    ...         'claim_group_process', 'underwriting_claim', 'process_rule',
    ...         'claim_eligibility'])
    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)
    >>> test_import_processes()
