# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, coog_date

__all__ = [
    'Benefit',
    'Claim',
    'ClaimService',
    'DeliverBenefit',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    underwriting_type = fields.Many2One('underwriting.type',
        'Underwriting Type', ondelete='RESTRICT')
    underwriting_delay = fields.Integer('Underwriting Delay (Days)', states={
            'invisible': ~Eval('underwriting_type')},
        depends=['underwriting_type'])


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
        Underwriting.delete(Underwriting.search(
                [('on_object', 'in', [str(x) for x in claims])]))
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
                if not service.benefit.underwriting_type:
                    continue
                date = loss.start_date
                if service.benefit.underwriting_delay:
                    date = coog_date.add_day(date,
                        service.benefit.underwriting_delay)
                for elem in service.underwritings:
                    if elem.effective_decision_date == date:
                        break
                else:
                    found = existing.get(service.benefit.underwriting_type,
                        None)
                    if found:
                        update[found].append((date, service))
                    else:
                        missing[service.benefit.underwriting_type].append(
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
    def activate_underwritings_if_needed(cls, claims, date):
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
                {'claims': '\n'.join([x.claim.rec_name
                            for x in draft_underwritings])})
            processed = list({x.underwriting for x in draft_underwritings})
            Underwriting.process(processed)
            return processed


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    underwritings = fields.Function(
        fields.Many2Many('underwriting.result', None, None, 'Underwritings',
            states={'invisible': ~Eval('underwritings')}),
        'get_appliable_underwritings')

    @classmethod
    def get_appliable_underwritings(cls, services, name):
        decisions = Pool().get('underwriting.result').search([
                ('target', 'in', [str(x) for x in services]),
                ('state', '!=', 'abandonned'),
                ('underwriting.state', '!=', 'draft'),
                ], order=[('effective_decision_date', 'ASC')])
        result = defaultdict(list)
        for decision in decisions:
            result[decision.target.id].append(decision.id)
        return result


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
