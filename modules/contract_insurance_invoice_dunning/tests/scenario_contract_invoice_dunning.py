# #Title# #Contract Insurance Invoice Dunning Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from proteus import config, Model, Wizard
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.modules.account.tests.tools import create_fiscalyear, \
    create_chart, get_accounts
from trytond.modules.account_invoice.tests.tools import \
    set_fiscalyear_invoice_sequences
from trytond.modules.contract_insurance_invoice.tests.tools import \
    add_invoice_configuration
from trytond.modules.offered.tests.tools import init_product
from trytond.modules.offered_insurance.tests.tools import \
    add_insurer_to_product
from trytond.modules.party_cog.tests.tools import create_party_person
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.premium.tests.tools import add_premium_rules

config = config.set_trytond()
config.pool.test = True

# #Comment# #Install Modules
Module = Model.get('ir.module')
contract_dunning_module = Module.find([
        ('name', '=', 'contract_insurance_invoice_dunning')])[0]
contract_dunning_module.click('install')
Wizard('ir.module.install_upgrade').execute('upgrade')

# #Comment# #Create country
_ = create_country()

# #Comment# #Create currenct
currency = get_currency(code='EUR')

# #Comment# #Create Company
_ = create_company(currency=currency)
company = get_company()

# #Comment# #Reload the context
User = Model.get('res.user')
config._context = User.get_preferences(True, config.context)

# #Comment# #Create Fiscal Year
fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear(company))
fiscalyear.click('create_period')

# #Comment# #Create chart of accounts
_ = create_chart(company)
accounts = get_accounts(company)

# #Comment# #Create Fee
AccountKind = Model.get('account.account.type')
dunning_fee_kind = AccountKind()
dunning_fee_kind.name = 'Dunning Fee Account Kind'
dunning_fee_kind.company = company
dunning_fee_kind.save()
Account = Model.get('account.account')
dunning_fee_account = Account()
dunning_fee_account.name = 'Dunning Fee Account'
dunning_fee_account.code = 'dunning_fee_account'
dunning_fee_account.kind = 'revenue'
dunning_fee_account.party_required = True
dunning_fee_account.type = dunning_fee_kind
dunning_fee_account.company = company
dunning_fee_account.save()
Product = Model.get('product.product')
Template = Model.get('product.template')
template = Template()
Uom = Model.get('product.uom')
unit, = Uom.find([('name', '=', 'Unit')])
template.default_uom = unit
template.name = 'Dunning Fee Template'
template.type = 'service'
template.list_price = Decimal(0)
template.cost_price = Decimal(0)
template.account_revenue = dunning_fee_account
template.save()
product_product = Product()
product_product.name = 'Dunning Fee Product'
product_product.template = template
product_product.default_uom = template.default_uom
product_product.type = 'service'
product_product.save()
Fee = Model.get('account.fee')
fee = Fee()
fee.name = 'Test Fee'
fee.code = 'test_fee'
fee.type = 'fixed'
fee.amount = Decimal('22')
fee.frequency = 'once_per_invoice'
fee.product = product_product
fee.save()

# #Comment# #Create dunning procedure
Procedure = Model.get('account.dunning.procedure')
procedure = Procedure(name='Procedure')
level = procedure.levels.new()
level.name = 'Reminder'
level.sequence = 1
level.days = 30
level = procedure.levels.new()
level.name = 'Formal Demand'
level.sequence = 2
level.days = 60
level = procedure.levels.new()
level.name = 'Suspend contract'
level.sequence = 2
level.days = 90
level.contract_action = 'hold'
level.dunning_fee = fee
level = procedure.levels.new()
level.name = 'Terminate contract'
level.sequence = 3
level.days = 100
level.contract_action = 'terminate'
level.termination_mode = 'at_last_posted_invoice'
procedure.save()

# #Comment# #Create Product
product = init_product()
product = add_quote_number_generator(product)
product = add_premium_rules(product)
product = add_invoice_configuration(product, accounts)
product = add_insurer_to_product(product)
product.dunning_procedure = procedure
product.save()


# #Comment# #Create Subscriber
subscriber = create_party_person()

# #Comment# #Create Contract
contract_start_date = datetime.date.today()
Contract = Model.get('contract')
ContractPremium = Model.get('contract.premium')
BillingInformation = Model.get('contract.billing_information')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = contract_start_date
contract.product = product
contract.billing_informations.append(BillingInformation(date=None,
        billing_mode=product.billing_modes[0],
        payment_term=product.billing_modes[0].allowed_payment_terms[0]))
contract.contract_number = '123456789'
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

# #Comment# #Create first invoice
ContractInvoice = Model.get('contract.invoice')
Contract.first_invoice([contract.id], config.context)
first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
first_invoice.invoice.click('post')

# #Comment# #Create dunnings at 30 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=30)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning, = Dunning.find([])
dunning.contract == contract
# #Res# #True
dunning.procedure == procedure
# #Res# #True

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True
contract.dunning_status
# #Res# #u'Reminder'
dunning_contracts = Contract.find([('dunning_status', '=', 'Reminder')])
len(dunning_contracts)
# #Res# #1

# #Comment# #Create dunnings at 60 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=60)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning, = Dunning.find(['state', '=', 'draft'])

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True

# #Comment# #Create dunnings at 90 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=90)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning, = Dunning.find(['state', '=', 'draft'])

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True
contract.status == 'hold'
# #Res# #True

fee_invoice, = ContractInvoice.find([('contract', '=', contract.id),
        ('non_periodic', '=', True)])
fee_invoice.invoice.total_amount == Decimal('22')
# #Res# #True

# #Comment# #Create dunnings at 100 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=100)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning = Dunning.find([('state', '=', 'draft')])[0]

# #Comment# #Process dunnning
Wizard('account.dunning.process', [dunning]).execute('process')
dunning.reload()
dunning.state == 'done'
# #Res# #True
contract.end_date == first_invoice.end
# #Res# #True
