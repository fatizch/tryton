##Title##Contract Subscription Scenario
##Comment##Imports
from proteus import config, Model, Wizard
##Comment##Constants
NEEDED_MODULES = [
    'account_payment_cog',
    'loan',
    'life_billing_collective_fr',
    'party_cog',
    'life_contract_subscription',
    'insurance_contract',
    'endorsement',
    'health_fr',
    'commission',
    'company_cog',
    'distribution',
    'account_payment_sepa_cog',
    'life_claim_process',
    'insurance_collection',
    'claim_process',
    'billing_individual',
    'insurance_contract_subscription',
    'currency_cog',
    'coop_utils',
    'cog_translation',
    'collection',
    'bank_cog',
    'commission_group',
    'insurance_collective_subscription',
    'task_manager',
    'rule_engine',
    'life_contract',
    'distribution_product',
    'offered',
    'contract',
    'table',
    'property_product',
    'country_cog',
    'life_claim',
    'contract_cash_value',
    'process',
    'insurance_collective',
    'insurance_product',
    'account_payment',
    'life_product',
    'health',
    'process_cog',
    'offered_cash_value',
    'bank_fr',
    'loan_claim',
    'party_fr',
    'claim',
    'billing',
    'account_cog',
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
wizard = Wizard('ir.test_case.run')
wizard.form.select_all_test_cases = True
wizard.form.select_all_files = True
wizard.execute('execute_test_cases')
wizard.execute('end')
Product = Model.get('offered.product')
len(Product.find([], order=[('code', 'ASC')]))
##Res##9
