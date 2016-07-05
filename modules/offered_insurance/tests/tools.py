# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model


def create_insurer(name=None):
    "Create default insurer"
    Party = Model.get('party.party')
    Insurer = Model.get('insurer')
    if not name:
        name = 'Insurer'
    insurer_party = Party(name=name, is_company=True)
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
