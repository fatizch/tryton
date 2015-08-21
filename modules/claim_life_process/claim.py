from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Claim',
    'Loss',
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

    def get_indemnifications(self, name=None):
        res = []
        for loss in self.losses:
            for service in loss.services:
                for indemnification in service.indemnifications:
                    res.append(indemnification.id)
        return res

    def get_is_pending_indemnification(self, name):
        for loss in self.losses:
            for del_ser in loss.services:
                for indemn in del_ser.indemnifications:
                    if indemn.status == 'calculated':
                        return True
        return False


class Loss:
    __name__ = 'claim.loss'

    @classmethod
    def __setup__(cls):
        super(Loss, cls).__setup__()
        cls.benefits.on_change_with.add('covered_person')
