#-*- coding:utf-8 -*-
import copy
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields

__all__ = [
    'LifeClaim',
    'LifeLoss',
    'LifeClaimDeliveredService',
]


class LifeClaim():
    'Claim'

    __name__ = 'ins_claim.claim'
    __metaclass__ = PoolMeta

    @classmethod
    def get_possible_contracts_from_party(cls, party, at_date):
        res = super(LifeClaim, cls).get_possible_contracts_from_party(party,
            at_date)
        if not party:
            return res
        CoveredElement = Pool().get('ins_contract.covered_element')
        cov_elems = CoveredElement.search([('person', '=', party.id)])
        for cov_elem in cov_elems:
            res.append(cov_elem.get_contract())
        return res


class LifeLoss():
    'Life Loss'

    __name__ = 'ins_claim.loss'
    __metaclass__ = PoolMeta

    covered_person = fields.Many2One('party.party', 'Covered Person',
        #TODO: Claimant could be a different person than covered person
        domain=[('id', '=', Eval('_parent_claim', {}).get('claimant'))])


class LifeClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    @classmethod
    def __setup__(cls):
        super(LifeClaimDeliveredService, cls).__setup__()
        cls.subscribed_service = copy.copy(cls.subscribed_service)
        if not cls.subscribed_service.domain:
            cls.subscribed_service.domain = []
        domain = ('covered_data.covered_element.person', '=',
            Eval('_parent_loss', {}).get('covered_person'))
        cls.subscribed_service.domain.append(domain)

    def get_covered_person(self):
        return self.loss.covered_person

    def init_dict_for_rule_engine(self, cur_dict):
        super(LifeClaimDeliveredService, self).init_dict_for_rule_engine(
            cur_dict)
        cur_dict['covered_person'] = self.get_covered_person()

    def get_covered_data(self):
        for covered_data in self.subscribed_service.covered_data:
            if covered_data.covered_element.person == self.get_covered_person:
                return covered_data
