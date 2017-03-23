# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import PoolMeta
from trytond.modules.planned_event import planned_event

__all__ = [
    'OptionDescription',
    ]


class OptionDescription(planned_event.EventPlanningConfigurationMixin):
    __metaclass__ = PoolMeta
    __name__ = 'offered.option.description'
