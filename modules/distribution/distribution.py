from trytond.modules.coop_utils import model, fields

__all__ = [
    'DistributionNetwork',
    ]


class DistributionNetwork(model.CoopSQL, model.CoopView):
    'Distribution Network'

    __name__ = 'distribution.dist_network'

    name = fields.Char('Name')
    parent = fields.Many2One('distribution.dist_network',
        'Top Level', select=True, left="left", right="right")
    childs = fields.One2Many('distribution.dist_network',
        'parent', 'Sub Levels')
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
