# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Bool

from trytond.modules.coog_core import fields, coog_date, model

__all__ = [
    'Contract',
    'Option',
    'CoveredElement',
    ]


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    is_group = fields.Function(
        fields.Boolean('Group Contract'),
        'get_is_group', searcher='search_is_group')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        cls.subscriber.domain = ['AND', cls.subscriber.domain,
            [If(
                    Bool(Eval('is_group')),
                    ('is_person', '=', False),
                    (),
                    )]
            ]
        cls.subscriber.depends += ['is_group']

    def get_is_group(self, name):
        return self.product.is_group if self.product else False

    @classmethod
    def search_is_group(cls, name, clause):
        return [('product.is_group', ) + tuple(clause[1:])]


class Option:
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    is_group = fields.Function(
        fields.Boolean('Group Option'),
        'on_change_with_is_group')

    @fields.depends('coverage')
    def on_change_with_is_group(self, name=None):
        if not self.coverage:
            return False
        return self.coverage.is_group


class CoveredElement:
    __metaclass__ = PoolMeta
    __name__ = 'contract.covered_element'

    contract_exit_date = fields.Date('Contract Exit Date', states={
            'invisible': ~Eval('manual_end_date')},
        depends=['manual_end_date'])
    subscriber = fields.Function(
        fields.Many2One('party.party', 'Subscriber'),
        'getter_subscriber')

    @classmethod
    def __setup__(cls):
        super(CoveredElement, cls).__setup__()
        cls.party.domain = ['AND', cls.party.domain, [
                If(
                    Eval('item_kind') == 'subsidiary',
                    (('is_person', '=', False),
                        ('parent_company', '=', Eval('subscriber'))),
                    ())]]
        cls.party.depends += ['subscriber', 'item_kind']
        cls.party.states['invisible'] &= (Eval('item_kind') != 'subsidiary')
        cls.party.states['required'] |= (Eval('item_kind') == 'subsidiary')
        cls.name.states['invisible'] |= (Eval('item_kind') == 'subsidiary')
        cls._buttons.update({
                'button_open_sub_elements': {
                    'readonly': ~Eval('has_sub_covered_elements'),
                    },
                })

    @classmethod
    def create(cls, vlist):
        Event = Pool().get('event')
        covered_elements = super(CoveredElement, cls).create(vlist)
        Event.notify_events([x for x in covered_elements if x.parent],
            'new_enrollment')
        return covered_elements

    @classmethod
    def write(cls, *args):
        Event = Pool().get('event')
        params = iter(args)
        terminated, modified = [], []
        for instances, values in zip(params, params):
            if 'end_reason' not in values:
                modified += [x for x in instances if x.parent]
            else:
                for record in instances:
                    if record.manual_end_date:
                        modified.append(record)
                    else:
                        terminated.append(record)
        super(CoveredElement, cls).write(*args)
        if terminated:
            Event.notify_events(terminated, 'terminated_enrollment')
        if modified:
            Event.notify_events(modified, 'changed_enrollment')

    @classmethod
    def view_attributes(cls):
        return super(CoveredElement, cls).view_attributes() + [(
                '/form//group[@id="invisible"]',
                'states',
                {'invisible': True},
                ),
            ]

    @fields.depends('contract_exit_date', 'manual_end_date')
    def on_change_manual_end_date(self):
        self.contract_exit_date = self.manual_end_date

    @fields.depends('item_kind')
    def on_change_with_icon(self, name=None):
        if self.item_kind == 'subsidiary':
            return 'coopengo-company'
        return super(CoveredElement, self).on_change_with_icon(name)

    def getter_subscriber(self, name):
        return self.contract.subscriber.id

    @fields.depends('contract')
    def on_change_contract(self):
        super(CoveredElement, self).on_change_contract()
        if self.contract:
            self.subscriber = self.contract.subscriber

    @classmethod
    def transfer_sub_covered(cls, matches, at_date):
        '''
            Copies sub covered elements from one covered element to another.
            The `matches` dictionary uses the source element as key and the
            target as value.
        '''
        new_elements = []
        for source, target in matches.iteritems():
            to_move = cls.search([
                    ('parent', '=', source.id),
                    ['OR', ('manual_end_date', '=', None),
                        ('manual_end_date', '>', at_date)],
                    ])
            if not to_move:
                continue
            new_elements += cls.copy(to_move, default={
                    'parent': target.id,
                    'manual_start_date': coog_date.add_day(at_date, 1)})
            cls.write(to_move, {'manual_end_date': at_date})
        Event = Pool().get('event')
        if new_elements:
            Event.notify_events(new_elements, 'transferred_enrollment')
        return new_elements

    @classmethod
    @model.CoogView.button_action('contract_group.act_open_sub_elements')
    def button_open_sub_elements(cls, instances):
        pass
