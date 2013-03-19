#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta

from trytond.modules.coop_utils import utils
from trytond.modules.insurance_contract import contract
from .collective import GroupRoot

__all__ = [
    'Contract',
    'GroupContract',
    'GroupOption',
    'GroupCoveredElement',
    'GroupCoveredData',
    'GroupBillingManager',
    'GroupPriceLine',
]

CONTRACT_KIND = [
    ('ind', 'Individual'),
    ('group', 'Group'),
]


class Contract():
    'Contract'

    __name__ = 'ins_contract.contract'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'billing_manager',
            [('kind', '=', cls.get_contract_kind())])
        super(Contract, cls).__setup__()

    @classmethod
    def get_contract_kind(cls):
        return 'ind'

    def new_billing_manager(self):
        res = super(Contract, self).new_billing_manager()
        res.kind = self.__class__.get_contract_kind()
        return res


class GroupContract(GroupRoot, contract.Contract):
    'Group Contract'

    __name__ = 'ins_collective.contract'

    enrollments = fields.One2Many('ins_collective.enrollment', 'gbp',
        'Enrollments')

    @classmethod
    def __setup__(cls):
        cls.options = copy.copy(cls.options)
        cls.options.model_name = 'ins_collective.option'

        cls.covered_elements = copy.copy(cls.covered_elements)
        cls.covered_elements.model_name = 'ins_collective.covered_element'

        cls.billing_manager = copy.copy(cls.billing_manager)
        cls.billing_manager.field = 'group_contract'

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

    @classmethod
    def get_contract_kind(cls):
        return 'group'

    def new_billing_manager(self):
        res = super(GroupContract, self).new_billing_manager()
        res.kind = self.__class__.get_contract_kind()
        return res


class GroupOption(GroupRoot, contract.Option):
    'Subscribed Coverage'

    __name__ = 'ins_collective.option'

    @classmethod
    def __setup__(cls):
        cls.contract = copy.copy(cls.contract)
        cls.contract.model_name = 'ins_collective.contract'

        cls.covered_data = copy.copy(cls.covered_data)
        cls.covered_data.model_name = 'ins_collective.covered_data'
        super(GroupOption, cls).__setup__()


class GroupCoveredElement(GroupRoot, contract.CoveredElement):
    'Covered Element'

    __name__ = 'ins_collective.covered_element'

    @classmethod
    def __setup__(cls):
        cls.contract = copy.copy(cls.contract)
        cls.contract.model_name = 'ins_collective.contract'

        cls.covered_data = copy.copy(cls.covered_data)
        cls.covered_data.model_name = 'ins_collective.covered_data'

        cls.parent = copy.copy(cls.parent)
        cls.parent.model_name = 'ins_collective.covered_element'

        cls.sub_covered_elements = copy.copy(cls.sub_covered_elements)
        cls.sub_covered_elements.model_name = 'ins_collective.covered_element'
        super(GroupCoveredElement, cls).__setup__()


class GroupCoveredData(GroupRoot, contract.CoveredData):
    'Covered Data'

    __name__ = 'ins_collective.covered_data'

    @classmethod
    def __setup__(cls):
        cls.option = copy.copy(cls.option)
        cls.option.model_name = 'ins_collective.option'

        cls.coverage = copy.copy(cls.coverage)
        cls.coverage.model_name = 'ins_collective.coverage'

        cls.covered_element = copy.copy(cls.covered_element)
        cls.covered_element.model_name = 'ins_collective.covered_element'

        super(GroupCoveredData, cls).__setup__()


class GroupBillingManager():
    'Billing Manager'

    __name__ = 'ins_contract.billing_manager'
    __metaclass__ = PoolMeta

    kind = fields.Selection(CONTRACT_KIND, 'Kind', required=True)
    group_contract = fields.Many2One('ins_collective.contract',
        'Group Contract')

    def get_contract(self):
        if self.kind == 'ind':
            return super(GroupBillingManager, self).get_contract()
        else:
            return self.group_contract


class GroupPriceLine():
    'Price Line'

    __name__ = 'ins_contract.price_line'
    __metaclass__ = PoolMeta

    @classmethod
    def get_line_target_models(cls):
        res = super(GroupPriceLine, cls).get_line_target_models()
        res.append(('ins_collective.covered_data', 'Collective Covered Data'))
        return res
