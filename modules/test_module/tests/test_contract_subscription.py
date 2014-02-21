# -*- coding: utf-8 -*-
##Title##Contract Subscription Scenario
##Comment##Imports
import os
import datetime
from proteus import config, Model, Wizard
##Comment##Create Database
# config = config.set_trytond(database_type='sqlite')
# config.pool.test = True
config = config.set_trytond(database_type='postgresql',
    database_name='test_1_database',
    user='admin',
    language='en_US',
    password='admin',
    config_file=os.path.join(os.environ['VIRTUAL_ENV'], 'tryton-workspace',
        'conf', 'trytond.conf'))
Module = Model.get('ir.module.module')
test_module = Module.find([('name', '=', 'test_module')])[0]
Module.install([test_module.id], config.context)
wizard = Wizard('ir.module.module.install_upgrade')
wizard.execute('upgrade')
##Comment##Import Exported DB
wizard = Wizard('ir.test_case.run')
wizard.form.select_all_test_cases = True
wizard.execute('execute_test_cases')
wizard.form.select_all_files = True
wizard.execute('execute_test_cases')
wizard.execute('end')
##Comment##Get Models
Product = Model.get('offered.product')
OptionDescription = Model.get('offered.option.description')
DistributionNetwork = Model.get('distribution.network')
Process = Model.get('process')
IrModel = Model.get('ir.model')
Contract = Model.get('contract')
Party = Model.get('party.party')
User = Model.get('res.user')
##Comment##Reload user preferences
config._context = User.get_preferences(True, config.context)
# Model.reset()
##Comment##Start subscription
wizard = Wizard('contract.subscribe')
dist_network = DistributionNetwork.find([('name', '=', 'Capvie')])[0]
wizard.form.dist_network = dist_network
product = Product.find([('code', '=', 'PREV')])[0]
product.name
##Res##u'Pr\xe9voyance Indviduelle'
wizard.form.product = product
process = Process.find([
        ('for_products', '=', wizard.form.product.id),
        ('kind', '=', 'subscription'),
        ('on_model', '=', IrModel.find([('model', '=', 'contract')])[0].id),
        ])[0]
wizard.form.good_process = process
process.fancy_name
##Res##u'Processus de souscription individuel'
wizard.execute('action')
##Comment##Get contract
contract = Contract.find([], limit=1, order=[('create_date', 'DESC')])[0]
contract.current_state.step.fancy_name
##Res##u'Produit'
result = 'Should Fail'
try:
    Contract._proxy._button_next_1([contract.id], {
            'running_process': 'individual_subscription'})
    result = True
except:
    pass
result
##Res##'Should Fail'
contract.current_state.step.fancy_name
##Res##u'Produit'
subscriber = Party.find([('is_person', '=', True),
        ('birth_date', '<=', datetime.date(1990, 1, 1))])[0]
contract.subscriber = subscriber
contract.save()
Contract._proxy._button_next_1([contract.id], {
        'running_process': 'individual_subscription'})
contract.current_state.step.fancy_name
##Res##u'Personnes Couvertes'
Contract._proxy._button_next_1([contract.id], {
        'running_process': 'individual_subscription'})
contract.reload()
contract.current_state.step.fancy_name
##Res##u'Garanties'
len(contract.covered_elements)
##Res##1
covered_element = contract.covered_elements[0]
covered_element.party.id == subscriber.id
##Res##True
len(covered_element.covered_data)
##Res##3
cd1 = covered_element.covered_data[0]
cd1.option.offered.code
##Res##u'INCAP'
cd1.coverage_amount_selection = '1234'
try:
    cd1.save()
    result = True
except:
    pass
result
##Res##'Should Fail'
cd1.__class__.get_possible_amounts([cd1.id], {})
##Res##[[('', ''), (u'60,00 \u20ac', u'60,00 \u20ac'), (u'110,00 \u20ac', u'110,00 \u20ac'), (u'160,00 \u20ac', u'160,00 \u20ac'), (u'210,00 \u20ac', u'210,00 \u20ac')]]
cd1.coverage_amount_selection = '110.00'
cd1.save()
cd2 = covered_element.covered_data[1]
cd2.option.offered.code
##Res##u'DC'
cd2.__class__.get_possible_amounts([cd2.id], {})
##Res##[[('', ''), (u'25000,00 \u20ac', u'25000,00 \u20ac'), (u'50000,00 \u20ac', u'50000,00 \u20ac'), (u'75000,00 \u20ac', u'75000,00 \u20ac'), (u'100000,00 \u20ac', u'100000,00 \u20ac')]]
cd2.coverage_amount_selection = '75000.00'
cd2.save()
# import pdb;pdb.set_trace()
