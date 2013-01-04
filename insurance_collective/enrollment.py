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
#        An enrollment represents the contract of an employee of a society
#        with the insurance society, which uses the GBP contract of the society
#        as a product.
#    '''
    __name__ = 'ins_collective.enrollment'

    gbp = fields.Many2One('ins_collective.gbp_contract', 'GBP Contract',
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
    'Option'
#    '''
#        Options on Enrollments are slightly different than standard options as
#        they use GBP coverages rather than standard coverages.
#    '''
    __name__ = 'ins_collective.option'

    is_subscribed = fields.Function(fields.Boolean('Subscribe ?',
            states={'readonly': Bool(Eval('id', -1) >= 0)}),
        'get_is_subscribed', 'set_is_subscribed')

    def get_is_subscribed(self, name=None):
        return self.id > 0 or (self.coverage and
            self.coverage.subscription_behaviour in ['mandatory', 'proposed'])

    @classmethod
    def set_is_subscribed(cls, options, name, value):
        pass

    @classmethod
    def create(cls, vals):
        if vals['is_subscribed']:
            return super(EnrollmentOption, cls).create(vals)
