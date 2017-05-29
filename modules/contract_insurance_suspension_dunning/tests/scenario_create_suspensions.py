# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Contract Insurance Invoice Dunning Scenario
# #Comment# #Imports
import datetime
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from proteus import Model, Wizard
from trytond.tests.tools import activate_modules
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
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

# #Comment# #Install Modules
config = activate_modules('contract_insurance_suspension_dunning')

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
level.name = 'Suspend contract'
level.sequence = 1
level.overdue = datetime.timedelta(30)
level.contract_action = 'hold'
level.dunning_fee = fee
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
contract_start_date = datetime.date.today() - relativedelta(days=10)
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
contract.billing_information.direct_debit is False
# #Res# #True

# #Comment# #Create first invoice
ContractInvoice = Model.get('contract.invoice')
Contract.first_invoice([contract.id], config.context)
first_invoice, = ContractInvoice.find([('contract', '=', contract.id)])
first_invoice.invoice.click('post')

# #Comment# #Create dunnings at 90 days
create_dunning = Wizard('account.dunning.create')
create_dunning.form.date = contract_start_date + relativedelta(days=90)
create_dunning.execute('create_')
Dunning = Model.get('account.dunning')
dunning, = Dunning.find(['state', '=', 'draft'])

# #Comment# #Process dunning
config.context['client_defined_date'] = create_dunning.form.date
Wizard('account.dunning.process', [dunning]).execute('process')
contract.status == 'hold'
# #Res# #True

dunning.reload()

Suspension = Model.get('contract.right_suspension')
suspension, = Suspension.find([])
suspension.start_date == dunning.last_process_date
# #Res# #True
suspension.type_ == 'definitive'
# #Res# #True
suspension.end_date == None
# #Res# #True

# Create temporary suspension
temporary_suspension = Suspension()
temporary_suspension.contract = contract
temporary_suspension.type_= 'temporary'
temporary_suspension.start_date = datetime.date.today()
temporary_suspension.click('button_activate')
temporary_suspension.save()

active_suspensions = Model.get('contract.right_suspension').find([])
len(active_suspensions) == 2
# #Res# #True

# #Comment# #Reactivate Contract
Wizard('contract.activate', models=[contract]).execute('apply')
contract.reload()

# #Comment# #Temporary suspension should now have a end_date and should be inactive
inactive_suspensions = Model.get('contract.right_suspension').find([('active',
    '=', False)])
len(inactive_suspensions) == 1
# #Res# #True

active_suspensions = Model.get('contract.right_suspension').find([])
len(active_suspensions) == 2
# #Res# #True

active_suspensions[-1].start_date - relativedelta(days=1) == \
    inactive_suspensions[0].end_date
# #Res# #True

# #Comment# #Definitive suspension should now have an end_date
active_suspensions[0].end_date == datetime.date.today() + relativedelta(days=1)
# #Res# #True

# #Comment# #Definitive suspension should now have an end_date
inactive_suspensions[0].end_date == datetime.date.today() + \
    relativedelta(days=1)
# #Res# #True
