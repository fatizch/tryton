# Needed for storing and displaying objects
from trytond.model import ModelSQL, ModelView
from trytond.model import fields as fields

# Needed for getting models
from trytond.pool import Pool

from trytond.modules.coop_utils import get_descendents

from trytond.modules.insurance_contract import Contract

__all__ = [
        'Enrollment',
        ]


class Enrollment(Contract):
    '''
        An enrollment represents the contract of an employee of a company
        with the insurance company, which uses the GBP contract of the company
        as a product.
    '''
    __name__ = 'ins_collective.enrollment'

    on_contract = fields.Many2One(
        'ins_collective.gbp_contract',
        'GBP Contract')
