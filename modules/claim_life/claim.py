#-*- coding:utf-8 -*-
import copy

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Loss',
    'DeliveredService',
    'ClaimIndemnification',
    ]


class Loss:
    __name__ = 'claim.loss'

    possible_covered_persons = fields.Function(
        fields.One2Many('party.party', None, 'Covered Persons',
            states={'invisible': True}),
        'on_change_with_possible_covered_persons')
    covered_person = fields.Many2One('party.party', 'Covered Person',
        #TODO: Temporary hack, the function field is not calculated
        #when storing the object
        domain=[If(
                Bool(Eval('possible_covered_persons')),
                ('id', 'in', Eval('possible_covered_persons')),
                ()
                )
            ], depends=['possible_covered_persons'])

    @classmethod
    def super(cls):
        super(Loss, cls).super()
        cls.main_loss = copy.copy(cls.main_loss)
        cls.main_loss.on_change.add('covered_person')

    def on_change_main_loss(self):
        res = super(Loss, self).on_change_main_loss()
        if self.main_loss and self.main_loss.covered_person:
            res['covered_person'] = self.main_loss.covered_person.id
        else:
            res['covered_person'] = None
        return res

    def get_possible_covered_persons(self):
        res = []
        CoveredElement = Pool().get('contract.covered_element')
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.claim.claimant, self.start_date):
            res.extend(covered_element.get_covered_parties(self.start_date))
        return res

    @fields.depends('claim', 'start_date')
    def on_change_with_possible_covered_persons(self, name=None):
        return [x.id for x in self.get_possible_covered_persons()]

    @fields.depends('covered_person', 'possible_loss_descs', 'claim',
        'start_date', 'loss_desc', 'event_desc')
    def on_change_covered_person(self):
        res = {}
        res['possible_loss_descs'] = self.on_change_with_possible_loss_descs()
        return res


class DeliveredService:
    __name__ = 'contract.service'

    def get_covered_person(self):
        return self.loss.covered_person

    def init_dict_for_rule_engine(self, cur_dict):
        super(DeliveredService, self).init_dict_for_rule_engine(
            cur_dict)
        cur_dict['covered_person'] = self.get_covered_person()

    def get_covered_data(self):
        party = self.get_covered_person()
        for covered_data in self.option.covered_data:
            sub_covered_data = covered_data.get_covered_data(party=party)
            if sub_covered_data:
                return sub_covered_data


class ClaimIndemnification:
    __name__ = 'claim.indemnification'

    def get_beneficiary(self, beneficiary_kind, del_service):
        res = super(ClaimIndemnification, self).get_beneficiary(
            beneficiary_kind, del_service)
        if beneficiary_kind == 'covered_person':
            res = del_service.loss.covered_person
        return res
