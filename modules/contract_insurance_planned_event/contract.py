# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.modules.report_engine import Printable

__all__ = [
    'Contract',
    'ContractOption',
    ]


class ContractOption(Printable):
    __metaclass__ = PoolMeta
    __name__ = 'contract.option'

    def update_planned_events(self, context_=None):
        context_ = context_ or {}
        self.init_dict_for_rule_engine(context_)
        return self.coverage.update_planned_events(context_, [self])


class Contract:
    __metaclass__ = PoolMeta
    __name__ = 'contract'

    @classmethod
    def _calculate_methods(cls, product):
        return super(Contract, cls)._calculate_methods(product) + [
            ('contract', 'update_planned_events')]

    def do_update_planned_events(self):
        actions = {
            'save': [],
            'delete': [],
            }
        for option in list(set(self.covered_element_options + self.options)):
            option_actions = option.update_planned_events()
            actions['save'] += option_actions['save']
            actions['delete'] += option_actions['delete']
        return actions

    @classmethod
    def update_planned_events(cls, contracts):
        to_save = []
        to_delete = []
        PlannedEvent = Pool().get('planned.event')
        for actions in [c.do_update_planned_events() for c in contracts]:
            to_save += actions['save']
            to_delete += actions['delete']
        if to_delete:
            PlannedEvent.delete(to_delete)
        if to_save:
            PlannedEvent.save(to_save)
        return to_save

    @classmethod
    def endorsement_update_planned_events(cls, contracts, caller=None):
        cls.update_planned_events(contracts)

    @classmethod
    def _calculate_methods_after_endorsement(cls):
        return super(Contract, cls
            )._calculate_methods_after_endorsement() | {
                'endorsement_update_planned_events'}
