# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
# #Title# #Add covered element and advance contract
# #Comment# #Imports
import datetime

from proteus import Model, Wizard

from trytond.tests.tools import activate_modules
from trytond.modules.company.tests.tools import get_company
from trytond.modules.company_cog.tests.tools import create_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.offered_insurance.tests.tools import init_product, \
    init_coverage
from trytond.modules.contract.tests.tools import add_quote_number_generator
from trytond.modules.country_cog.tests.tools import create_country
from trytond.modules.party_cog.tests.tools import create_party_person

from trytond.modules.coog_core.test_framework import execute_test_case, \
    switch_user

config = activate_modules(['contract_term_renewal'])
_ = create_country()

currency = get_currency(code='EUR')
_ = create_company(currency=currency)
company = get_company()

execute_test_case('authorizations_test_case')

product = init_product(user_context=False)
coverage2 = init_coverage(company=company, name='Test Coverage 2')
product.coverages.append(coverage2)
product = add_quote_number_generator(product)
product.save()
renewal_rule = product.term_renewal_rule.new()
renewal_rule.allow_renewal = True
Rule = Model.get('rule_engine')
subscription_date_sync_rule, = Rule.find([
        ('short_name', '=', 'product_term_renewal_sync_sub_date')])
renewal_rule.rule = subscription_date_sync_rule
renewal_rule.product = product
renewal_rule.save()
product.save()

config = switch_user('contract_user')

product = Model.get('offered.product')(product.id)

company = get_company()
product = Model.get('offered.product')(product.id)

subscriber = create_party_person(name="DUPONT", first_name="MARTIN")
subscriber.code = '2579'
subscriber.save()

Contract = Model.get('contract')
contract = Contract()
contract.company = company
contract.subscriber = subscriber
contract.start_date = datetime.date(2019, 1, 1)
contract.product = product
contract.save()
Wizard('contract.activate', models=[contract]).execute('apply')

assert contract.status == 'active'
assert len(contract.options) == 2
assert [(x.status, x.sub_status, x.end_date) for x in contract.options] == [
    ('active', None, contract.end_date), ('active', None, contract.end_date)], [
        (x.status, x.sub_status, x.end_date) for x in contract.options]

contract_end_date = datetime.date(2019, 3, 31)
contract.end_date = contract_end_date
contract.save()
contract.reload()
assert contract.end_date == contract_end_date

SubStatus = Model.get('contract.sub_status')
terminated, = SubStatus.find([('code', '=', 'terminated')])
termination_wizard = Wizard('contract.stop', models=[contract])
termination_wizard.form.status = 'terminated'
termination_wizard.form.sub_status = terminated
termination_wizard.form.at_date = contract_end_date
termination_wizard.execute('stop')
contract.reload()
assert contract.end_date == contract_end_date


wiz = Wizard('contract.reactivate', models=[contract])
wiz.execute('reactivate')

contract.reload()
assert contract.end_date == datetime.date(2019, 12, 31)
assert contract.status == 'active'
assert [(x.status, x.sub_status, x.end_date) for x in contract.options] == [
    ('active', None, contract.end_date), ('active', None, contract.end_date)], [
        (x.status, x.sub_status, x.end_date) for x in contract.options]
