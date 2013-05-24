from trytond.modules.coop_utils import model, fields

__all__ = [
    'DistributionNetwork',
    ]


class DistributionNetwork(model.CoopSQL, model.CoopView):
    'Distribution Network'

    __name__ = 'distribution.dist_network'

    name = fields.Char('Name')
    top_level = fields.Many2One('distribution.dist_network',
        'Top Level')
    sub_levels = fields.One2Many('distribution.dist_network',
        'top_level', 'Sub Levels')
