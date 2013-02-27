#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pyson import Eval

from trytond.modules.insurance_contract import contract
from .collective import GroupRoot
from trytond.modules.coop_utils import utils

__all__ = [
        'GroupContract',
        'GroupOption',
        'GroupCoveredElement',
        'GroupCoveredData',
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
