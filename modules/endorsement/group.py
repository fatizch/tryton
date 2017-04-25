
# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import model, fields
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'Group',
    ]


class Group(model.CoogSQL, model.CoogView):
    "Group"
    __name__ = "res.group"
    endorsement_definitions = fields.Many2Many('endorsement.definition-res.group',
        'group', 'definition', 'Endorsement Definition')
