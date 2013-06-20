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
    payment_lines = fields.Function(
        fields.One2Many('account.payment', None, 'Payment Lines',
            domain=[
                ('line.move.origin', '=', (__name__, Eval('id', 0))),
                ('state', 'in', ('approved', 'processing', 'succeeded'))],
            on_change_with=['id'], loading='lazy'),
        'on_change_with_payment_lines')

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

    def on_change_with_payment_lines(self, name=None):
        return map(lambda x: x.id, sorted(utils.get_domain_instances(self,
            'payment_lines'), key=lambda x: x.date, reverse=True))
