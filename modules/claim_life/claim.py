# -*- coding:utf-8 -*-
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Loss',
    'ClaimService',
    'ClaimServiceExtraDataRevision',
    ]


class Loss:
    __name__ = 'claim.loss'

    possible_covered_persons = fields.Function(
        fields.One2Many('party.party', None, 'Covered Persons',
            states={'invisible': True}),
        'on_change_with_possible_covered_persons')
    covered_person = fields.Many2One('party.party', 'Covered Person',
        # TODO: Temporary hack, the function field is not calculated
        # when storing the object
        domain=[If(
                Bool(Eval('possible_covered_persons')),
                ('id', 'in', Eval('possible_covered_persons')),
                ()
                )
            ], ondelete='RESTRICT', depends=['possible_covered_persons'])

    def get_possible_covered_persons(self):
        res = []
        CoveredElement = Pool().get('contract.covered_element')
        if not self.claim:
            return []
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
        self.possible_loss_descs = self.on_change_with_possible_loss_descs()

    @classmethod
    def add_func_key(cls, values):
        # Update without func_key is not handled for now
        values['_func_key'] = None

    @property
    def date(self):
        return self.start_date

    def get_covered_person(self):
        if hasattr(self, 'loss_desc') and self.loss_desc and hasattr(
                self, 'covered_person'):
            if self.loss_desc.loss_kind == 'life':
                return self.covered_person

    def get_all_extra_data(self, at_date):
        CoveredElement = Pool().get('contract.covered_element')
        res = super(Loss, self).get_all_extra_data(at_date)
        if not self.claim:
            return res
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.covered_person, self.start_date):
            if (covered_element.party and
                    covered_element.party == self.covered_person and
                    covered_element.main_contract == self.claim.main_contract):
                res.update(covered_element.get_all_extra_data(self.start_date))
        return res


class ClaimService:
    __name__ = 'claim.service'

    def get_covered_person(self):
        if self.loss.loss_desc.loss_kind == 'life':
            return self.loss.covered_person
        return super(ClaimService, self).get_covered_person()

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(
            cur_dict)
        if self.loss.loss_desc.loss_kind == 'life':
            cur_dict['covered_person'] = self.get_covered_person()


class ClaimServiceExtraDataRevision:
    __name__ = 'claim.service.extra_data'

    @classmethod
    def get_extra_data_summary(cls, extra_datas, name):
        res = super(ClaimServiceExtraDataRevision, cls).get_extra_data_summary(
            extra_datas, name)
        for instance, desc in res.iteritems():
            new_data = {}
            for line in desc.splitlines():
                key, value = line.split(' : ')
                if ' M-' in key:
                    new_key = key.split(' M-')[0]
                    if new_key not in new_data:
                        new_data[new_key] = Decimal(value) \
                            if value != 'None' else 0
                    else:
                        new_data[new_key] += Decimal(value) \
                            if value != 'None' else 0
                else:
                    new_data[key] = value
            res[instance] = '\n'.join(('%s : %s' % (k, v) for k, v in
                    new_data.iteritems()))
        return res
