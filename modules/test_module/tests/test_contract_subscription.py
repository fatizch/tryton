##Title##Contract Subscription Scenario
##Comment##Imports
from proteus import config, Model, Wizard
##Comment##Constants
NEEDED_MODULES = [
    'coop_translation',
    'coop_party',
    'coop_party_fr',
    'coop_bank',
    'bank_fr',
    'table',
    'health_fr',
    'property_product',
    'life_contract_subscription',
    'task_manager',
    'coop_process',
    'life_claim_process',
    'loan_claim',
    'insurance_collective_subscription',
    'commission',
    'commission_collective',
    'billing',
    'billing_individual',
    'coop_account_payment',
    'coop_account_payment_sepa',
    'life_billing_collective_fr',
    'insurance_collection',
    'cash_value_contract',
    ]
##Comment##Create Database
config = config.set_trytond(database_type='sqlite')
config.pool.test = True
Module = Model.get('ir.module.module')
coop_utils_modules = Module.find([('name', 'in', NEEDED_MODULES)])
for module in coop_utils_modules:
    Module.install([module.id], config.context)
Wizard('ir.module.module.install_upgrade').execute('upgrade')
##Comment##Import Exported DB
wizard = Wizard('coop_utils.test_case_wizard')
wizard.form.select_all_files = True
wizard.execute('execute_test_cases')
wizard.execute('end')
Product = Model.get('offered.product')
len(Product.find([], order=[('code', 'ASC')]))
##Res##9
