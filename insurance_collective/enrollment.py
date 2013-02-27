import copy
from trytond.model import fields
from trytond.pyson import Eval, Bool

from trytond.modules.insurance_collective import GroupRoot
from trytond.modules.insurance_contract import Contract
from trytond.modules.insurance_contract import Option

__all__ = [
        'Enrollment',
        'EnrollmentOption',
        ]


class Enrollment(GroupRoot, Contract):
    'Enrollment'
#    '''
#        An enrollment represents the contract of an employee of a company
#        with the insurance company, which uses the GBP contract of the company
#        as a product.
#    '''
    __name__ = 'ins_collective.enrollment'

    gbp = fields.Many2One('ins_collective.contract', 'GBP Contract',
        on_change=['gbp', 'start_date', 'options'])

    @classmethod
    def __setup__(cls):
        super(Enrollment, cls).__setup__()
        cls.subscriber = copy.copy(cls.subscriber)
        cls.subscriber.string = 'Affiliated'

    def on_change_gbp(self):
        res = {}
        res['product'] = None
        res['options'] = []
        if not self.gbp:
            return res
        if self.gbp.final_product:
            res['product'] = self.gbp.final_product[0].id
            options = []
            for coverage in self.gbp.final_product[0].options:
                option = {}
                option['start_date'] = self.start_date
                option['coverage'] = coverage.id
                options.append(option)
            res['options'] = {'add': options}
        return res


class EnrollmentOption(GroupRoot, Option):
    'Subscribed Option'
#    '''
#        Options on Enrollments are slightly different than standard options as
#        they use GBP coverages rather than standard coverages.
#    '''
    __name__ = 'ins_collective.enrollment_option'

    is_subscribed = fields.Function(fields.Boolean('Subscribe ?',
            states={'readonly': Bool(Eval('id', -1) >= 0)}),
        'get_is_subscribed', 'set_is_subscribed')

    def get_is_subscribed(self, name=None):
        return self.id > 0 or (self.offered and
            self.offered.subscription_behaviour in ['mandatory', 'proposed'])

    @classmethod
    def set_is_subscribed(cls, options, name, value):
        pass

    @classmethod
    def create(cls, vals):
        for option in vals:
            if option['is_subscribed']:
                return super(EnrollmentOption, cls).create([option])
