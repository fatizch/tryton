===============================
Contract Subscription Scenario
===============================

Imports::

    >>> import os
    >>> import datetime
    >>> from proteus import config, Model, Wizard

Create Database::

    >>> config = config.set_trytond(database_type='postgresql',
    ...     database_name='test_1_database',
    ...     user='admin',
    ...     language='en_US',
    ...     password='admin',
    ...     config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
    ...         'conf', 'trytond.conf'))
    >>> Module = Model.get('ir.module.module')
    >>> test_module = Module.find([('name', '=', 'test_module')])[0]
    >>> Module.install([test_module.id], config.context)
    >>> wizard = Wizard('ir.module.module.install_upgrade')
    >>> wizard.execute('upgrade')

Import Exported DB::

    >>> TestCaseConfig = Model.get('ir.test_case')(1)
    >>> TestCaseConfig.language = Model.get('ir.lang').find([
    ...         ('code', '=', 'fr_FR')])[0]
    >>> TestCaseConfig.save()
    >>> wizard = Wizard('ir.test_case.run')
    >>> wizard.form.select_all_test_cases = True
    >>> wizard.execute('execute_test_cases')
    >>> wizard.form.select_all_files = True
    >>> wizard.execute('execute_test_cases')
    >>> wizard.execute('end')

Get Models::

    >>> Product = Model.get('offered.product')
    >>> OptionDescription = Model.get('offered.option.description')
    >>> Process = Model.get('process')
    >>> IrModel = Model.get('ir.model')
    >>> Contract = Model.get('contract')
    >>> Party = Model.get('party.party')
    >>> User = Model.get('res.user')

Reload user preferences::

    >>> config._context = User.get_preferences(True, config.context)

Start subscription::

    >>> wizard = Wizard('contract.subscribe')
    >>> product = Product.find([('code', '=', 'PREV')])[0]
    >>> product.name
    u'Pr\xe9voyance Indviduelle'
    >>> wizard.form.product = product
    >>> process = Process.find([
    ...         ('for_products', '=', wizard.form.product.id),
    ...         ('kind', '=', 'subscription'),
    ...         ('on_model', '=', IrModel.find([('model', '=', 'contract')])[0].id),
    ...         ])[0]
    >>> wizard.form.good_process = process
    >>> process.fancy_name
    u'Processus de souscription individuel'
    >>> wizard.execute('action')

Get contract::

    >>> contract = Contract.find([], limit=1, order=[('create_date', 'DESC')])[0]
    >>> contract.current_state.step.fancy_name
    u'Produit'
    >>> result = 'Should Fail'
    >>> try:
    ...     Contract._proxy._button_next_1([contract.id], {
    ...             'running_process': 'individual_subscription'})
    ...     result = True
    ... except:
    ...     pass
    >>> result
    'Should Fail'
    >>> contract.current_state.step.fancy_name
    u'Produit'
    >>> subscriber = Party.find([('is_person', '=', True),
    ...         ('birth_date', '<=', datetime.date(1990, 1, 1))])[0]
    >>> contract.subscriber = subscriber
    >>> contract.save()
    >>> Contract._proxy._button_next_1([contract.id], {
    ...         'running_process': 'individual_subscription'})
    >>> contract.current_state.step.fancy_name
    u'Personnes Couvertes'
    >>> Contract._proxy._button_next_1([contract.id], {
    ...         'running_process': 'individual_subscription'})
    >>> contract.reload()
    >>> contract.current_state.step.fancy_name
    u'Garanties'
    >>> len(contract.covered_elements)
    1
    >>> covered_element = contract.covered_elements[0]
    >>> covered_element.party.id == subscriber.id
    True
    >>> len(covered_element.covered_data)
    3
    >>> cd1 = covered_element.covered_data[0]
    >>> cd1.option.offered.code
    u'INCAP'
    >>> cd1.coverage_amount_selection = '1234'
    >>> try:
    ...     cd1.save()
    ...     result = True
    ... except:
    ...     pass
    >>> result
    'Should Fail'
    >>> cd1.__class__.get_possible_amounts([cd1.id], {})
    [[('', ''), (u'60,00 \u20ac', u'60,00 \u20ac'), (u'110,00 \u20ac', u'110,00 \u20ac'), (u'160,00 \u20ac', u'160,00 \u20ac'), (u'210,00 \u20ac', u'210,00 \u20ac')]]
    >>> cd1.coverage_amount_selection = '110.00'
    >>> cd1.save()
    >>> cd2 = covered_element.covered_data[1]
    >>> cd2.option.offered.code
    u'DC'
    >>> cd2.__class__.get_possible_amounts([cd2.id], {})
    [[('', ''), (u'25 000,00 \u20ac', u'25 000,00 \u20ac'), (u'50 000,00 \u20ac', u'50 000,00 \u20ac'), (u'75 000,00 \u20ac', u'75 000,00 \u20ac'), (u'100 000,00 \u20ac', u'100 000,00 \u20ac')]]
    >>> cd2.coverage_amount_selection = '75000.00'
    >>> cd2.save()
