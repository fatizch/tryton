# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from trytond.modules.offered.tests.tools import init_product, init_coverage


def create_insurer(name=None):
    "Create default insurer"
    Party = Model.get('party.party')
    Insurer = Model.get('insurer')
    if not name:
        name = 'Insurer'
    insurer_party = Party(name=name)
    insurer_party.save()
    insurer = Insurer()
    insurer.party = insurer_party
    insurer.save()
    return insurer


def add_insurer_to_product(product, name=None):
    insurer = create_insurer(name)
    for coverage in product.coverages:
        coverage.insurer = insurer
    return product


def init_person_coverage(name=None, start_date=None, company=None):
    ItemDescription = Model.get('offered.item.description')
    item_description = ItemDescription()
    item_description.name = 'Test Item Description'
    item_description.code = 'test_item_description'
    item_description.kind = 'person'
    item_description.save()
    coverage = init_coverage('test_person_coverage', start_date, company)
    coverage.item_desc = item_description
    return coverage


def init_insurance_product(name=None, start_date=None,
        company=None, user_context=False):
    product = init_product(name, start_date, company, user_context)
    person_coverage = init_person_coverage(start_date, company)
    product.coverages.append(person_coverage)
    add_insurer_to_product(product)
    return product
