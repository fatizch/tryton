##Title##Contract Subscription Scenario
##Comment##Imports
import os
from proteus import config, Model, Wizard
##Comment##Constants
NEEDED_MODULES = [
    'coop_translation',
    'party_bank',
    'table',
    'health_fr',
    'property_product',
    'life_contract_subscription',
    'task_manager',
    'coop_process',
    'life_claim_process',
    'loan_claim',
    'life_contract_collective',
    'insurance_collective_subscription',
    'commission',
    'billing',
    'coop_account_payment',
    'coop_account_payment_sepa',
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
import_wizard = Wizard('coop_utils.import_wizard')
with open(os.path.abspath(os.path.normpath(os.path.join(
                    __file__, '..', 'exported_db.json'))), 'r') as f:
    file_content = f.read()
    import_wizard.form.selected_file = file_content
    import_wizard.execute('file_import')
Product = Model.get('offered.product')
len(Product.find([], order=[('code', 'ASC')]))
##Res##9
