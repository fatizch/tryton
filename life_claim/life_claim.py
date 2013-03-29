#-*- coding:utf-8 -*-
import copy
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool

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
        for cov_elem in cls.get_possible_covered_elements(party, at_date):
            contract = cov_elem.get_contract()
            if contract:
                res.append(contract)
        return res

    @classmethod
    def get_possible_covered_elements(cls, party, at_date):
        CoveredElement = Pool().get('ins_contract.covered_element')
        #TODO : To enhance with date control
        return CoveredElement.search([('person', '=', party.id)])


class LifeLoss():
    'Life Loss'

    __name__ = 'ins_claim.loss'
    __metaclass__ = PoolMeta

    possible_covered_persons = fields.Function(
        fields.One2Many('party,party', None, 'Covered Persons',
            states={'invisible': True},
        ), 'get_possible_covered_persons_ids')
    covered_person = fields.Many2One('party.party', 'Covered Person',
        #TODO: Temporary hack, the function field is not calculated
        #when storing the object
        domain=[
            If(
                Bool(Eval('possible_covered_persons')),
                ('id', 'in', Eval('possible_covered_persons')),
                ()
            )
        ],
        depends=['possible_covered_persons'])

    def get_possible_covered_persons(self):
        res = []
        for covered_element in self.claim.get_possible_covered_elements(
                self.claim.claimant, self.start_date):
            res.extend(covered_element.get_covered_persons(self.start_date))
        return res

    def get_possible_covered_persons_ids(self, name):
        return [x.id for x in self.get_possible_covered_persons()]


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
            #TODO to enhance the covered person could be the spouse or the
            #children of the insured person
            if (covered_data.covered_element.person ==
                    self.get_covered_person()):
                return covered_data
