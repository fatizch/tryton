# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from proteus import Model
from trytond.modules.company.tests.tools import get_company
from trytond.modules.currency.tests.tools import get_currency
from trytond.modules.coog_core.test_framework import switch_user

__all__ = ['create_contract_generator', 'init_product', 'init_coverage']


def create_contract_generator(company=None, user_context=False):
    "Create contract generator "
    Sequence = Model.get('ir.sequence')
    SequenceType = Model.get('ir.sequence.type')

    if not company:
        company = get_company()

    sequence_code = SequenceType(
        name='Product sequence',
        code='contract')
    sequence_code.save()
    contract_sequence = Sequence(
        name='Contract Sequence',
        code='contract',
        company=company.id)
    contract_sequence.save()
    return contract_sequence


def init_coverage(name=None, start_date=None, company=None):
    OptionDescription = Model.get('offered.option.description')

    if not company:
        company = get_company()
    if not name:
        name = 'Test Coverage'
    if not start_date:
        start_date = datetime.date(2014, 1, 1)

    return OptionDescription(
        name=name,
        code=name,
        company=company.id,
        start_date=start_date,
        currency=get_currency(code='EUR'),
        subscription_behaviour='mandatory')


def init_product(name=None, start_date=None, company=None, user_context=False):
    if user_context:
        switch_user('product_user')
    Product = Model.get('offered.product')
    if not company:
        company = get_company()
    if not name:
        name = 'Test Product'
    if not start_date:
        start_date = datetime.date(2014, 1, 1)

    contract_sequence = create_contract_generator(company, user_context)
    product = Product(
        name=name,
        code=name,
        company=company.id,
        currency=get_currency(code='EUR'),
        contract_generator=contract_sequence.id,
        start_date=start_date)
    coverage = init_coverage(start_date=start_date, company=company)
    product.coverages.append(coverage)
    return product
