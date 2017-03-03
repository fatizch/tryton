# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, utils
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Benefit',
    'Claim',
    'ClaimService',
    'DeliverBenefit',
    ]


class Benefit(get_rule_mixin('underwriting_rule', 'Underwriting Rule')):
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls.underwriting_rule.domain = [('type_', '=', 'underwriting_type')]

    def do_calculate_underwritings(self, data):
        if not self.underwriting_rule:
            return None, None
        code, date = self.calculate_underwriting_rule(data)
        if code:
            type_ = Pool().get('underwriting.type').get_type_from_code(code)
        else:
            type_ = None
        return type_, date


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    underwritings = fields.Function(
        fields.Many2Many('underwriting', None, None, 'Underwritings'),
        'get_underwritings')

    @classmethod
    def __setup__(cls):
        super(Claim, cls).__setup__()
        cls._error_messages.update({
                'must_activate_underwritings': 'It is necessary to activate '
                'underwritings for the following claims before going on:\n\n'
                '%(claims)s',
                })

    @classmethod
    def delete(cls, claims):
        Underwriting = Pool().get('underwriting')
        to_clean = Underwriting.search(
            [('on_object', 'in', [str(x) for x in claims])])
        if to_clean:
            Underwriting.delete(to_clean)
        super(Claim, cls).delete(claims)

    @classmethod
    def get_underwritings(cls, claims, name):
        Underwriting = Pool().get('underwriting')
        result = defaultdict(list)
        for elem in Underwriting.search([
                    ('on_object', 'in', [str(x) for x in claims])]):
            result[elem.on_object.id].append(elem.id)
        return result

    @classmethod
    def update_underwritings(cls, claims):
        Underwriting = Pool().get('underwriting')
        to_create, to_save, to_close, to_delete = [], [], [], []
        for claim in claims:
            if claim.status == 'closed':
                tmp_close, tmp_delete = claim.close_underwritings()
                to_close += tmp_close
                to_delete += tmp_delete
            else:
                tmp_save, tmp_create = claim.calculate_underwritings()
                to_create += tmp_create
                to_save += tmp_save
        if to_create or to_save or to_close:
            Underwriting.save(to_create + to_save + to_close)
        if to_close:
            Underwriting.complete(to_close)
        if to_delete:
            Underwriting.delete(to_delete)

    def calculate_underwritings(self):
        pool = Pool()
        Result = pool.get('underwriting.result')
        existing = {x.type_: x
            for x in self.underwritings if x.state != 'completed'}
        missing = defaultdict(list)
        update = defaultdict(list)
        for loss in self.losses:
            for service in loss.services:
                type_, date = service.get_underwriting_data()
                if not type_:
                    continue
                for elem in service.underwritings:
                    if elem.effective_decision_date == date:
                        break
                else:
                    found = existing.get(type_, None)
                    if found:
                        update[found].append((date, service))
                    else:
                        missing[type_].append(
                            (date, service))
        to_create, to_save = [], []
        for underwriting_type, services in missing.iteritems():
            new_underwriting = underwriting_type.new_underwriting(self,
                self.claimant, services)
            to_create.append(new_underwriting)
        for underwriting, services in update.iteritems():
            to_add = []
            for date, service in services:
                new_decision = Result()
                new_decision.underwriting = underwriting
                new_decision.target = service
                new_decision.effective_decision_date = date
                new_decision.on_change_underwriting()
                to_add.append(new_decision)
            underwriting.results = list(underwriting.results) + to_add
            to_save.append(underwriting)
        return to_save, to_create

    def close_underwritings(self):
        to_close = set()
        to_delete = []
        for underwriting in self.underwritings:
            if underwriting.state == 'draft':
                to_delete.append(underwriting)
                continue
            if underwriting.state != 'processing':
                continue
            for result in underwriting.results:
                if result.state != 'waiting':
                    continue
                result.abandon()
                to_close.add(underwriting)
        return list(to_close), to_delete

    @classmethod
    def close(cls, claims, sub_status, date=None):
        super(Claim, cls).close(claims, sub_status, date=None)
        cls.update_underwritings(claims)

    @classmethod
    def deliver_automatic_benefit(cls, claims):
        super(Claim, cls).deliver_automatic_benefit(claims)
        cls.update_underwritings(claims)

    def ws_add_new_loss(self, loss_desc_code, parameters=None):
        super(Claim, self).ws_add_new_loss(loss_desc_code, parameters)
        self.update_underwritings([self])

    @classmethod
    def activate_underwritings_if_needed(cls, claims, date=None):
        if not date:
            date = utils.today()
        pool = Pool()
        Underwriting = pool.get('underwriting')
        Result = pool.get('underwriting.result')
        domain = [('underwriting.on_object', 'in', [str(x) for x in claims]),
            ('underwriting.state', '=', 'draft')]
        if date:
            domain += [('effective_decision_date', '<=', date)]
        draft_underwritings = Result.search(domain)
        if draft_underwritings:
            cls.raise_user_warning('must_activate_underwritings_%s' %
                claims[0].id, 'must_activate_underwritings',
                {'claims': '\n'.join({x.claim.rec_name
                            for x in draft_underwritings})})
            processed = list({x.underwriting for x in draft_underwritings})
            Underwriting.process(processed)
            return processed

    def init_dict_for_rule_engine(self, cur_dict):
        cur_dict['claim'] = self


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    underwritings = fields.Function(
        fields.Many2Many('underwriting.result', None, None, 'Underwritings',
            states={'invisible': ~Eval('underwritings')}),
        'get_appliable_underwritings')

    @classmethod
    def delete(cls, services):
        pool = Pool()
        Underwriting = pool.get('underwriting')
        UnderwritingResult = pool.get('underwriting.result')
        to_clean = UnderwritingResult.search(
            [('target', 'in', [str(x) for x in services])])
        if to_clean:
            underwritings = list({x.underwriting.id for x in to_clean})
            UnderwritingResult.delete(to_clean)
            to_delete = [x for x in Underwriting.browse(underwritings)
                if len(x.results) == 0]
            if to_delete:
                Underwriting.delete(to_delete)
        super(ClaimService, cls).delete(services)

    @classmethod
    def get_appliable_underwritings(cls, services, name):
        decisions = Pool().get('underwriting.result').search([
                ('target', 'in', [str(x) for x in services]),
                ('state', '!=', 'abandoned'),
                ('underwriting.state', '!=', 'draft'),
                ], order=[('effective_decision_date', 'ASC')])
        result = defaultdict(list)
        for decision in decisions:
            result[decision.target.id].append(decision.id)
        return result

    def get_underwriting_data(self):
        data_dict = {}
        self.init_dict_for_rule_engine(data_dict)
        return self.benefit.do_calculate_underwritings(data_dict)


class DeliverBenefit:
    __metaclass__ = PoolMeta
    __name__ = 'claim.deliver_benefits'

    def transition_deliver(self):
        result = super(DeliverBenefit, self).transition_deliver()
        claims = set()
        for elem in self.benefits.benefits_to_deliver:
            if not elem.to_deliver:
                continue
            claims.add(elem.loss.claim)
        if claims:
            Pool().get('claim').update_underwritings(claims)
        return result
