# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta

from trytond.modules.planned_event import planned_event
from trytond.modules.coog_core import coog_string

__all__ = [
    'OptionDescription',
    ]


class OptionDescription(planned_event.EventPlanningConfigurationMixin,
        metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    def get_documentation_structure(self):
        structure = super(OptionDescription, self).get_documentation_structure()
        planning_rule_desc = coog_string.doc_for_field(self, 'planning_rule',
            '')
        planning_rule_desc['attributes'] = []
        if self.planning_rule:
            structure['attributes'].append(
                self.get_planning_rule_rule_engine_documentation_structure())
        return structure
