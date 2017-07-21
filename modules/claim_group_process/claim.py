# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'ClaimDeclareFindProcess',
    'ClaimDeclare',
    ]


class ClaimDeclareFindProcess:
    __metaclass__ = PoolMeta
    __name__ = 'claim.declare.find_process'

    legal_entity = fields.Many2One('party.party', 'Legal Entity',
        domain=[('is_person', '=', False)])

    @fields.depends('claims', 'party', 'legal_entity')
    def on_change_party(self):
        super(ClaimDeclareFindProcess, self).on_change_party()
        if not self.party:
            self.legal_entity = None
        else:
            companies = self.party.companies
            if companies:
                self.legal_entity = companies[0].id


class ClaimDeclare:
    __metaclass__ = PoolMeta
    __name__ = 'claim.declare'

    @classmethod
    def __setup__(cls):
        super(ClaimDeclare, cls).__setup__()


    def init_main_object_from_process(self, obj, process_param):
        res, errs = super(ClaimDeclare,
            self).init_main_object_from_process(obj, process_param)
        if res:
            obj.legal_entity = process_param.legal_entity
        return res, errs
