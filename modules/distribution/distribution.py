from trytond.transaction import Transaction
from trytond.modules.coop_utils import model, fields

__all__ = [
    'DistributionNetwork',
    ]


class DistributionNetwork(model.CoopSQL, model.CoopView):
    'Distribution Network'

    __name__ = 'distribution.network'

    name = fields.Char('Name')
    parent = fields.Many2One('distribution.network', 'Top Level', select=True,
        left="left", right="right")
    childs = fields.One2Many('distribution.network', 'parent', 'Sub Levels')
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)

    @staticmethod
    def default_left():
        return 0

    @staticmethod
    def default_right():
        return 0

    @classmethod
    def _export_force_recreate(cls):
        result = super(DistributionNetwork, cls)._export_force_recreate()
        result.remove('childs')
        return result

    @classmethod
    def _export_skips(cls):
        res = super(DistributionNetwork, cls)._export_skips()
        res.add('left')
        res.add('right')
        return res

    def get_parents(self):
        return self.search([
                ('left', '<', self.left), ('right', '>', self.right)])

    @classmethod
    def _update_mptt(cls, field_names, list_ids, values=None):
        # MPTT update is rather long, and calling it once for each node is
        # expensive when updating hundreds of them. So we delay the computation
        # until the end of the import process
        if '__importing__' in Transaction().context:
            pass
        else:
            super(DistributionNetwork, cls)._update_mptt(field_names, list_ids,
                values)

    @classmethod
    def _post_import(cls, records):
        super(DistributionNetwork, cls)._update_mptt(['parent'],
            [[x.id for x in records]])
