#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool

from trytond.modules.coop_utils import fields

__all__ = [
    'LifeClaim',
    'LifeLoss',
    'LifeClaimDeliveredService',
    'LifeIndemnification',
]


class LifeClaim():
    'Claim'

    __name__ = 'ins_claim.claim'
    __metaclass__ = PoolMeta


class LifeLoss():
    'Life Loss'

    __name__ = 'ins_claim.loss'
    __metaclass__ = PoolMeta

    possible_covered_persons = fields.Function(
        fields.One2Many('party.party', None, 'Covered Persons',
            states={'invisible': True},
            on_change_with=['claim', 'start_date']
        ), 'on_change_with_possible_covered_persons')
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
        depends=['possible_covered_persons'],
        on_change=['covered_person', 'possible_loss_descs', 'claim',
            'start_date', 'loss_desc', 'event_desc'])

    @classmethod
    def super(cls):
        super(LifeLoss, cls).super()
        cls.main_loss = copy.copy(cls.main_loss)
        cls.main_loss.on_change += ['covered_person']

    def on_change_main_loss(self):
        res = super(LifeLoss, self).on_change_main_loss()
        if self.main_loss and self.main_loss.covered_person:
            res['covered_person'] = self.main_loss.covered_person.id
        else:
            res['covered_person'] = None
        return res

    def get_possible_covered_persons(self):
        res = []
        CoveredElement = Pool().get('ins_contract.covered_element')
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.claim.claimant, self.start_date):
            res.extend(covered_element.get_covered_parties(self.start_date))
        return res

    def on_change_with_possible_covered_persons(self, name=None):
        return [x.id for x in self.get_possible_covered_persons()]

    def on_change_covered_person(self):
        res = {}
        res['possible_loss_descs'] = self.on_change_with_possible_loss_descs()
        return res


class LifeClaimDeliveredService():
    'Claim Delivered Service'

    __name__ = 'ins_contract.delivered_service'
    __metaclass__ = PoolMeta

    def get_covered_person(self):
        return self.loss.covered_person

    def init_dict_for_rule_engine(self, cur_dict):
        super(LifeClaimDeliveredService, self).init_dict_for_rule_engine(
            cur_dict)
        cur_dict['covered_person'] = self.get_covered_person()

    def get_covered_data(self):
        party = self.get_covered_person()
        for covered_data in self.subscribed_service.covered_data:
            sub_covered_data = covered_data.get_covered_data(party=party)
            if sub_covered_data:
                return sub_covered_data


class LifeIndemnification():
    'Indemnification'

    __name__ = 'ins_claim.indemnification'
    __metaclass__ = PoolMeta

    def get_beneficiary(self, beneficiary_kind, del_service):
        res = super(LifeIndemnification, self).get_beneficiary(
            beneficiary_kind, del_service)
        if beneficiary_kind == 'covered_person':
            res = del_service.loss.covered_person
        return res
