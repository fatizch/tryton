#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.insurance_contract import contract
from .collective import GroupRoot

__all__ = [
    'GroupContract',
    'GroupOption',
    'GroupCoveredElement',
    'GroupCoveredData',
    'GroupBillingManager',
    'GroupPriceLine',
]


class GroupContract(GroupRoot, contract.Contract):
    'Group Contract'

    __name__ = 'ins_collective.contract'

    enrollments = fields.One2Many('ins_collective.enrollment', 'gbp',
        'Enrollments')

    @classmethod
    def __setup__(cls):
        super(GroupContract, cls).__setup__()
        cls.subscriber = copy.copy(cls.subscriber)
        if not cls.subscriber.domain:
            cls.subscriber.domain = []
        cls.subscriber.domain.append(('is_company', '=', True))
        cls.offered = copy.copy(cls.offered)
        if not cls.offered.context:
            cls.offered.context = {}
        cls.offered.context['subscriber'] = Eval('subscriber')
        if not cls.offered.depends:
            cls.offered.depends = []
        cls.offered.depends = ['subscriber']

    def get_rec_name(self, name=None):
        if self.contract_number:
            return self.contract_number
        return super(GroupContract, self).get_rec_name(name)


class GroupOption(GroupRoot, contract.Option):
    'Subscribed Coverage'

    __name__ = 'ins_collective.option'


class GroupCoveredElement(GroupRoot, contract.CoveredElement):
    'Covered Element'

    __name__ = 'ins_collective.covered_element'


class GroupCoveredData(GroupRoot, contract.CoveredData):
    'Covered Data'

    __name__ = 'ins_collective.covered_data'


class GroupBillingManager(GroupRoot, contract.BillingManager):
    'Billing Manager'

    __name__ = 'ins_collective.billing_manager'


class GroupPriceLine(GroupRoot, contract.PriceLine):
    'Price Line'

    __name__ = 'ins_collective.price_line'

    @classmethod
    def get_line_target_models(cls):
        res = super(GroupPriceLine, cls).get_line_target_models()
        res.append(('ins_collective.covered_data', 'Collective Covered Data'))
        return res
