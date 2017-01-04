# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, If, Bool, In
from trytond.modules.coog_core import fields

from datetime import timedelta

__all__ = [
    'Claim',
    'Loss',
    'ClaimService',
    'ClaimServiceExtraDataRevision',
    ]


class Claim:
    __metaclass__ = PoolMeta
    __name__ = 'claim'

    def add_new_relapse(self, loss_desc_code):
        self.add_new_loss(loss_desc_code, is_a_relapse=True)

    def add_new_long_term_disability(self, loss_desc_code):
        self.add_new_loss(loss_desc_code)
        assert self.losses[-1].loss_desc.code == loss_desc_code
        # Look for last short term loss and init the start date
        for loss in self.losses[-2::-1]:  # Python is fun
            if loss.loss_desc.loss_kind == 'std':
                self.losses[-1].initial_std_start_date = loss.start_date
                break


class Loss:
    __metaclass__ = PoolMeta
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
    std_start_date = fields.Function(fields.Date('STD Start Date',
            states={'invisible': Eval('loss_desc_kind') != 'std',
                'readonly': Eval('state') != 'draft'},
            depends=['loss_desc_kind', 'loss_desc', 'state']),
        'get_start_end_dates', setter='set_start_end_dates')
    std_end_date = fields.Function(fields.Date('STD End Date',
            states={'invisible': Eval('loss_desc_kind') != ('std')},
            depends=['loss_desc_kind', 'loss_desc']),
        'get_start_end_dates', setter='set_start_end_dates')
    initial_std_start_date = fields.Date('Initial STD Start Date',
        states={'invisible': Eval('loss_desc_kind') != 'ltd',
            'readonly': Eval('state') != 'draft'},
        depends=['loss_desc_kind', 'loss_desc', 'state'])
    ltd_start_date = fields.Function(fields.Date('LTD Start Date',
            states={'invisible': Eval('loss_desc_kind') != 'ltd'},
            depends=['loss_desc_kind', 'loss_desc']),
        'get_start_end_dates', setter='set_start_end_dates')
    ltd_end_date = fields.Function(fields.Date('LTD End Date',
            states={'invisible': Eval('loss_desc_kind') != 'ltd'},
            depends=['loss_desc_kind', 'loss_desc']),
        'get_start_end_dates', setter='set_start_end_dates')
    return_to_work_date = fields.Date('Return to Work',
        states={'invisible': ~Bool(Eval('return_to_work_date'))})
    is_a_relapse = fields.Boolean('Is A Relapse',
        states={'invisible': Eval('loss_desc_kind') != 'std'})

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls.start_date.states['invisible'] = cls.start_date.states.get(
            'invisible', False) | In(Eval('loss_desc_kind', ''),
            ['std', 'ltd'])
        cls.start_date.depends.append('loss_desc_kind')
        cls.end_date.states['invisible'] = cls.end_date.states.get(
            'invisible', False) | In(Eval('loss_desc_kind', ''),
            ['std', 'ltd'])
        cls.end_date.depends.append('loss_desc_kind')
        cls._error_messages.update({
                'relapse': 'Relapse',
                'missing_previous_loss': 'An inital std must be created in '
                'order to declare a relapse',
                'previous_loss_end_date_missing': "The previous std "
                "doesn't have an end date defined",
                'one_day_between_relapse_and_previous_loss': 'One day is '
                'required between the relapse and the previous std'
                })

    def get_start_end_dates(self, name):
        if 'start_date' in name:
            date = 'start_date'
        else:
            date = 'end_date'
        return getattr(self, date, None)

    @classmethod
    def set_start_end_dates(cls, losses, name, value):
        if 'start_date' in name:
            date = 'start_date'
        else:
            date = 'end_date'
        cls.write(losses, {date: value})

    def close(self, sub_status, date=None):
        super(Loss, self).close(sub_status, date)
        if date:
            self.return_to_work_date = date
            self.save()

    def get_rec_name(self, name=None):
        res = super(Loss, self).get_rec_name(name)
        if self.is_a_relapse:
            res = '%s (%s)' % (res, self.raise_user_error('relapse',
                raise_exception=False))
        return res

    def get_possible_covered_persons(self):
        res = []
        CoveredElement = Pool().get('contract.covered_element')
        if not self.claim or not self.start_date:
            return []
        for covered_element in CoveredElement.get_possible_covered_elements(
                self.claim.claimant, self.start_date):
            res.extend(covered_element.get_covered_parties(self.start_date))
        return res

    @fields.depends('claim', 'start_date')
    def on_change_with_possible_covered_persons(self, name=None):
        if not self.start_date:
            return []
        return [x.id for x in self.get_possible_covered_persons()]

    @fields.depends('covered_person', 'possible_loss_descs', 'claim',
        'start_date', 'loss_desc', 'event_desc')
    def on_change_covered_person(self):
        self.possible_loss_descs = self.on_change_with_possible_loss_descs()

    @fields.depends('return_to_work_date', 'end_date')
    def on_change_return_to_work_date(self):
        self.update_end_date()

    def update_end_date(self):
        if self.return_to_work_date and not self.end_date:
            self.end_date = self.return_to_work_date - timedelta(days=1)

    @classmethod
    def add_func_key(cls, values):
        # Update without func_key is not handled for now
        values['_func_key'] = None

    def init_loss(self, loss_desc_code, **kwargs):
        self.return_to_work_date = None
        self.end_date = None
        super(Loss, self).init_loss(loss_desc_code, **kwargs)
        self.covered_person = self.claim.claimant \
            if self.claim.claimant.is_person else None
        self.update_end_date()

    @property
    def date(self):
        return self.start_date

    def get_covered_person(self):
        return getattr(self, 'covered_person', None)

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

    def covered_options(self):
        Option = Pool().get('contract.option')
        person = self.get_covered_person()
        if person:
            return Option.get_covered_options_from_party(person,
                self.get_date() or self.claim.declaration_date)
        return super(Loss, self).covered_options()

    def pre_validate(self):
        super(Loss, self).pre_validate()
        if not self.is_a_relapse:
            return
        if self.claim.losses.index(self) == 0:
            self.raise_user_error('missing_previous_loss')
        if not self.start_date:
            return
        previous_loss = self.claim.losses[
            self.claim.losses.index(self) - 1]
        if not previous_loss.end_date:
            self.raise_user_error('previous_loss_end_date_missing')
        if (self.start_date - previous_loss.end_date).days <= 1:
            # As it's a relapse there must be one day of work betwwen two std
            self.raise_user_error(
                'one_day_between_relapse_and_previous_loss')

    @classmethod
    def get_possible_duplicates_fields(cls):
        return super(Loss, cls).get_possible_duplicates_fields() | {
            'covered_person',
            }

    def get_possible_duplicates_clauses(self):
        return super(Loss, self).get_possible_duplicates_clauses() + [
            ('covered_person', '=', self.covered_person.id),
            ]

    @classmethod
    def do_check_duplicates(cls):
        return True


class ClaimService:
    __metaclass__ = PoolMeta
    __name__ = 'claim.service'

    def get_covered_person(self):
        return self.loss.get_covered_person()

    def init_dict_for_rule_engine(self, cur_dict):
        super(ClaimService, self).init_dict_for_rule_engine(
            cur_dict)
        if self.loss.loss_desc.loss_kind == 'life':
            cur_dict['covered_person'] = self.get_covered_person()

    def init_from_loss(self, loss, benefit):
        super(ClaimService, self).init_from_loss(loss, benefit)
        if not loss.is_a_relapse:
            return
        values = self.extra_datas[-1].extra_data_values
        old_values = self.loss.claim.delivered_services[0].extra_datas[-1].\
            extra_data_values
        for key, value in old_values.iteritems():
            if key in values:
                values[key] = value
        self.extra_datas[-1].extra_data_values = values


class ClaimServiceExtraDataRevision:
    __metaclass__ = PoolMeta
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
