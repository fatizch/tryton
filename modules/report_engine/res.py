# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model, fields
from trytond.pool import PoolMeta

__all__ = [
    'Group',
    ]


class Group:
    __metaclass__ = PoolMeta
    __name__ = 'res.group'

    report_templates = fields.Many2Many('report.template-res.group',
        'group', 'report_template', 'Report Templates')
