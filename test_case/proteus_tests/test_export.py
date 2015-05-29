
from proteus import config, Model, Wizard

IMPORT_FILE = '/path/to/export_file.json'

NEEDED_MODULES = [
    'bank_cog',
    'table',
    'contract_insurance_health_fr',
    'offered_property_casualty',
    'contract_life_process',
    'task_manager',
    'process_cog',
    'claim_life_process',
    'claim_credit',
    'contract_group_process',
    'billing',
    'account_payment_cog',
    'account_payment_sepa_cog',
    ]


config = config.set_trytond(database='sqlite://')
config.pool.test = True

Module = Model.get('ir.module')
coop_utils_modules = Module.find([('name', 'in', NEEDED_MODULES)])
for module in coop_utils_modules:
    Module.install([module.id], config.context)
Wizard('ir.module.install_upgrade').execute('upgrade')

import_wizard = Wizard('ir.import')
with open(IMPORT_FILE, 'r') as f:
    file_content = f.read()
    import_wizard.form.selected_file = file_content
    import_wizard.execute('file_import')
