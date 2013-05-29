#-*- coding:utf-8 -*-
from trytond.pyson import Eval
from trytond.pool import PoolMeta
from trytond.pyson import If, Equal

from trytond.modules.coop_utils import utils

__all__ = [
    'GroupContract',
    ]


class GroupContract():
    'Group Contract'

    __name__ = 'contract.contract'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        utils.update_domain(cls, 'subscriber', [If(
                    Equal(Eval('kind'), 'group'),
                    ('is_company', '=', True),
                    (),
                    )])
        utils.update_depends(cls, 'subscriber', ['kind'])
        super(GroupContract, cls).__setup__()

    def init_from_offered(self, offered, start_date=None, end_date=None):
        res, errs = super(GroupContract, self).init_from_offered(offered,
            start_date, end_date)
        if res:
            self.kind = 'group' if offered.is_group else 'individual'
        return res, errs

    @classmethod
    def get_possible_contract_kind(cls):
        res = super(GroupContract, cls).get_possible_contract_kind()
        res.extend([
                ('individual', 'Individual'),
                ('group', 'Group'),
                ])
        return list(set(res))
