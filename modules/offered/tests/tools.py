import datetime
from proteus import Model
from trytond.modules.company.tests.tools import get_company

__all__ = ['create_contract_generator', 'create_product', 'create_coverage']


def create_contract_generator(company=None):
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
        company=company)
    contract_sequence.save()
    return contract_sequence


def create_coverage(name=None, start_date=None, company=None):
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
        company=company,
        start_date=start_date,
        subscription_behaviour='mandatory')


def create_product(name=None, start_date=None, company=None):
    Product = Model.get('offered.product')

    if not company:
        company = get_company()
    if not name:
        name = 'Test Product'
    if not start_date:
        start_date = datetime.date(2014, 1, 1)

    contract_sequence = create_contract_generator(company)
    product = Product(
        name=name,
        code=name,
        company=company,
        contract_generator=contract_sequence,
        start_date=start_date)
    coverage = create_coverage(start_date=start_date, company=company)
    product.coverages.append(coverage)
    return product
