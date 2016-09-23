# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields
from trytond.pyson import Eval

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    companies = fields.Function(
        fields.Many2Many('party.party', None, None, 'Companies',
            states={'invisible': ~Eval('is_person')},
            domain=[('is_person', '=', False)]),
        'get_companies')

    def get_companies(self, name):
        res = [covered.main_contract.subscriber.id
            for covered in self.covered_elements
            if not covered.main_contract.subscriber.is_person]
        return res
