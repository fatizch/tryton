from trytond.pool import PoolMeta, Pool

from trytond.pyson import If, Eval
from trytond.modules.coop_utils import utils, fields


__all__ = [
    'Contract',
]


class Contract():
    'Contract'

    __metaclass__ = PoolMeta
    __name__ = 'contract.contract'

    paid_today = fields.Function(fields.Numeric('Paid today'),
        'get_paid_today')
    due_today = fields.Function(fields.Numeric('Due today'),
        'get_due_today')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        utils.update_domain(cls, 'receivable_lines', [
            If(~Eval('display_all_lines'), ('payment_amount', '!=', 0), ())])

    def get_paid_today(self, name):
        return self.receivable_today - self.due_today

    def get_due_today(self, name):
        if not (hasattr(self, 'id') and self.id):
            return 0.0
        MoveLine = Pool().get('account.move.line')
        Date = Pool().get('ir.date')
        lines = MoveLine.search([
            ('account.kind', '=', 'receivable'),
            ('reconciliation', '=', None),
            ('move.origin', '=', '%s,%s' % (self.__name__, self.id)),
            ('maturity_date', '<=', Date.today())])
        result = sum(map(lambda x: x.payment_amount, lines))
        return result
