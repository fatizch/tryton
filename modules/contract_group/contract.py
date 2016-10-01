# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pyson import Eval
from trytond.pool import PoolMeta, Pool
from trytond.pyson import If, Bool

from trytond.modules.coog_core import fields, model

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
        cls._buttons.update({
                'button_add_enrollment': {
                    'invisible': ~Bool(Eval('is_group'))}
                })

    def get_is_group(self, name):
        return self.product.is_group if self.product else False

    @classmethod
    def search_is_group(cls, name, clause):
        return [('product.is_group', ) + tuple(clause[1:])]

    @classmethod
    @model.CoogView.button_action(
        'contract_group.act_create_enrollment_wizard')
    def button_add_enrollment(cls, contracts):
        pass


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
                modified += instances
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
