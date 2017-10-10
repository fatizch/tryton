==========================
Import Processes Scenario
==========================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.process_cog.tests.tools import test_import_processes
    >>> from trytond.modules.company.tests.tools import get_company
    >>> from trytond.modules.company_cog.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

Install Modules::

    >>> config = activate_modules(['claim_life_process', 'claim_salary_fr',
    ...     'note_authorizations', 'claim_eckert', 'claim_group_process',
    ...     'process_rule', 'claim_eligibility', 'underwriting_claim'])
    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)
    >>> _ = create_company(currency=get_currency(code='EUR'))
    >>> company = get_company()
    >>> test_import_processes()
