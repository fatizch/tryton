from trytond.transaction import Transaction
from trytond.modules.cog_utils import model, fields, coop_string

__all__ = [
    'DistributionNetwork',
    ]


class DistributionNetwork(model.CoopSQL, model.CoopView):
    'Distribution Network'

    __name__ = 'distribution.network'

    name = fields.Char('Name')
    code = fields.Char('Code', required=True)
    parent = fields.Many2One('distribution.network', 'Top Level', select=True,
        left="left", right="right", ondelete='CASCADE')
    childs = fields.One2Many('distribution.network', 'parent', 'Sub Levels')
    left = fields.Integer('Left', required=True, select=True)
    right = fields.Integer('Right', required=True, select=True)

    @classmethod
    def __setup__(cls):
        super(DistributionNetwork, cls).__setup__()
        cls._sql_constraints += [
            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
            ]

    @fields.depends('code', 'name')
    def on_change_with_code(self):
        if self.code:
            return self.code
        return coop_string.remove_blank_and_invalid_char(self.name)

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
