# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields

__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    ]


class Claim:
    __name__ = 'claim'

    indemnifications = fields.Function(
        fields.One2Many('claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications')
    indemnifications_consult = fields.Function(
        fields.One2Many('claim.indemnification', None, 'Indemnifications'),
        'get_indemnifications')
    is_pending_indemnification = fields.Function(
        fields.Boolean('Pending Indemnification', states={'invisible': True}),
        'get_is_pending_indemnification')
    indemnifications_to_schedule = fields.Function(
        fields.One2Many('claim.indemnification', None,
            'Indemnification To Schedule'),
        'get_indemnifications_to_schedule', setter='setter_void')
    has_calculated_indemnification = fields.Function(
        fields.Boolean('Has Calculated Indemnification'),
        'get_has_calculated_indemnification')

    def get_indemnifications(self, name=None):
        res = []
        for loss in self.losses:
            for service in loss.services:
                for indemnification in service.indemnifications:
                    res.append(indemnification.id)
        return res

    def get_has_calculated_indemnification(self, name=None):
        return any([x.status == 'calculated' for x in
                    self.indemnifications])

    def get_is_pending_indemnification(self, name):
        for loss in self.losses:
            for del_ser in loss.services:
                for indemn in del_ser.indemnifications:
                    if indemn.status == 'calculated':
                        return True
        return False

    def get_indemnifications_to_schedule(self, name):
        return [indemnification.id for indemnification in self.indemnifications
            if indemnification.status in ('calculated', 'scheduled')]
