from decimal import Decimal
from sql.aggregate import Sum
from sql.conditionals import Coalesce

from trytond.pool import PoolMeta, Pool

from trytond.transaction import Transaction
from trytond.pyson import If, Eval, Date
from trytond.modules.cog_utils import utils, fields


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]


class Contract:
    __name__ = 'contract'

    paid_today = fields.Function(fields.Numeric('Paid today'),
        'get_paid_today')
    due_today = fields.Function(fields.Numeric('Due today'),
        'get_due_today')
    payment_lines = fields.Function(
        fields.One2Many('account.payment', None, 'Payment Lines',
            depends=['display_all_lines', 'id'], domain=[
                ('line.move.origin', '=', (__name__, Eval('id', 0))),
                ('state', 'in', ('approved', 'processing', 'succeeded')),
                If(~Eval('display_all_lines'),
                    ('line.maturity_date', '<=',
                        Eval('context', {}).get(
                            'client_defined_date', Date())),
                    ())],
            loading='lazy'),
        'on_change_with_payment_lines')

    @classmethod
    def __setup__(cls):
        super(Contract, cls).__setup__()
        utils.update_domain(cls, 'receivable_lines', [
            If(~Eval('display_all_lines'), ('payment_amount', '!=', 0), ())])

    def get_due_today(self, name):
        res = self.receivable_today - self.paid_today
        return res

    @classmethod
    def get_paid_today(cls, contracts, name):
        res = {}
        pool = Pool()
        User = pool.get('res.user')
        Date = pool.get('ir.date')
        cursor = Transaction().cursor

        res = dict((p.id, Decimal('0.0')) for p in contracts)

        user_id = Transaction().user
        if user_id == 0 and 'user' in Transaction().context:
            user_id = Transaction().context['user']
        user = User(user_id)
        if not user.company:
            return res

        move_line = pool.get('account.move.line').__table__()
        payment = pool.get('account.payment').__table__()
        account = pool.get('account.account').__table__()
        move = pool.get('account.move').__table__()

        query_table = move_line.join(payment, type_='LEFT',
            condition=(move_line.id == payment.line)
            ).join(move,
            condition=(move.id == move_line.move)
            ).join(account, condition=(account.id == move_line.account))
        today_query = (move_line.maturity_date <= Date.today()) | (
            move_line.maturity_date == None)
        good_moves_query = move.id.in_(move.select(move.id, where=(
                    move.origin.in_(
                        ['contract,%s' % x.id for x in contracts]))))

        cursor.execute(*query_table.select(move.origin, Sum(
                    Coalesce(payment.amount, 0)),
                where=(account.active)
                & (account.kind == 'receivable')
                & (move_line.reconciliation == None)
                & good_moves_query
                & today_query
                & (account.company == user.company.id),
                group_by=move.origin))
        for contract_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[int(contract_id.split(',')[1])] = sum
        return res

    @fields.depends('display_all_lines', 'id')
    def on_change_with_payment_lines(self, name=None):
        return map(lambda x: x.id, sorted(utils.get_domain_instances(self,
            'payment_lines'), key=lambda x: x.date, reverse=True))
