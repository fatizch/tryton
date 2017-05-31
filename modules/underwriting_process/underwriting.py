# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CoogProcessFramework

__all__ = [
    'Underwriting',
    ]


class Underwriting(CoogProcessFramework):
    __metaclass__ = ClassAttr
    __name__ = 'underwriting'

    def get_task_name(self, name=None):
        # doesn't contain interesting information for now
        return ''
