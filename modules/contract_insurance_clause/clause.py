from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'ContractClause',
    ]


class ContractClause:
    __name__ = 'contract.clause'

    covered_data = fields.Many2One('contract.covered_data', 'Covered Data',
        ondelete='CASCADE', states={'invisible': ~Eval('covered_data')})

    @fields.depends('covered_data')
    def on_change_with_visual_text(self, name=None):
        if self.contract:
            return super(ContractClause, self).on_change_with_visual_text()
        else:
            good_version = self.clause.get_version_at_date(
                self.covered_data.contract.appliable_conditions_date)
            return good_version.content
