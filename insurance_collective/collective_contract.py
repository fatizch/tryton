#-*- coding:utf-8 -*-
from trytond.model import fields
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.pyson import If, Equal

from trytond.modules.coop_utils import utils

CONTRACT_KIND = [
    ('individual', 'Individual'),
    ('group', 'Group'),
    ('enrollment', 'Enrollment'),
]

__all__ = [
    'GroupContract',
    'GroupCoveredData',
]


class GroupContract():
    'Group Contract'

    __name__ = 'ins_contract.contract'
    __metaclass__ = PoolMeta

    kind = fields.Selection(CONTRACT_KIND, 'Kind', required=True)
    group_contract = fields.Many2One('ins_contract.contract',
        'Group Contract', domain=[('kind', '=', 'group')],
        states={'invisible': Eval('kind') != 'enrollment'})

    @classmethod
    def _setup__(cls):
        super(GroupContract, cls).__setup__()
        utils.update_domain(cls, 'subscriber',
            [
                (
                    'is_company',
                    'in',
                    If(Equal(Eval('kind'), 'group'), [True], [True, False])
                ),
            ])

        if not cls.subscriber.depends:
            cls.subscriber.depends = []
        cls.subscriber.depends.append('kind')

    def init_from_offered(self, offered, start_date=None, end_date=None,
            kind=None):
        res, errs = super(GroupContract, self).init_from_offered(offered,
            start_date, end_date)
        if res:
            if offered.is_group:
                self.kind = kind if kind else 'group'
            else:
                self.kind = 'individual'
        return res, errs


class GroupCoveredData():
    'Covered Data'

    __name__ = 'ins_contract.covered_data'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(GroupCoveredData, cls).__setup__()
