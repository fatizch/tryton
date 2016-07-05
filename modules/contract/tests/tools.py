# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from proteus import Model
from trytond.modules.company.tests.tools import get_company

__all__ = ['create_quote_number_generator', 'add_quote_number_generator']


def create_quote_number_generator(company=None):
    "Create quote number generator "
    Sequence = Model.get('ir.sequence')
    SequenceType = Model.get('ir.sequence.type')

    if not company:
        company = get_company()

    sequence_code = SequenceType(
        name='Quote Sequence',
        code='quote')
    sequence_code.save()
    quote_sequence = Sequence(
        name='Quote Sequence',
        code='quote',
        company=company)
    quote_sequence.save()
    return quote_sequence


def add_quote_number_generator(product):
    product.quote_number_sequence = create_quote_number_generator(
            product.company)
    return product
