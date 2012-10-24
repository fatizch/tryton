# Needed for storing and displaying objects
from trytond.model import fields

# Needed for getting models
from trytond.pool import Pool

from trytond.modules.coop_utils import get_descendents

from trytond.modules.insurance_contract import Contract
from trytond.modules.insurance_contract import Option

__all__ = [
        'Enrollment',
        'EnrollmentOption',
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

    options = fields.One2Many(
        'ins_collective.option',
        'contract',
        'Options')


class EnrollmentOption(Option):
    '''
        Options on Enrollments are slightly different than standard options as
        they use GBP coverages rather than standard coverages.
    '''
    __name__ = 'ins_collective.option'

    contract = fields.Many2One('ins_collective.enrollment',
                               'Contract',
                               ondelete='CASCADE')

    coverage = fields.Many2One('ins_collective.coverage',
                               'Offered Coverage',
                               required=True)
