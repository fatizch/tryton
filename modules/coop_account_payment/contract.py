from decimal import Decimal

from trytond.pool import PoolMeta, Pool

from trytond.transaction import Transaction
from trytond.pyson import If, Eval, Date
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
                ('state', 'in', ('approved', 'processing', 'succeeded')),
                If(~Eval('display_all_lines'),
                    ('line.maturity_date', '<=',
                        Eval('context', {}).get(
                            'client_defined_date', Date())),
                    ())],
            on_change_with=['display_all_lines', 'id'], loading='lazy'),
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
        company_id = user.company.id

        today_query = 'AND (l.maturity_date <= %s ' \
            'OR l.maturity_date IS NULL) '
        today_value = [Date.today()]

        cursor.execute('SELECT m.origin, '
                'SUM(COALESCE(p.amount, 0)) '
            'FROM account_move_line AS l '
            'LEFT JOIN account_payment p ON l.id = p.line '
            'JOIN account_account AS a ON a.id = l.account '
            'JOIN account_move AS m ON l.move = m.id  '
            'WHERE '
                'a.active '
                'AND a.kind = \'receivable\' '
                'AND m.id IN '
                    '(SELECT m.id FROM account_move as m '
                    'WHERE m.origin IN '
                    '(' + ','.join(('%s',) * len(contracts)) + ')) '
                'AND l.reconciliation IS NULL '
                + today_query +
                'AND a.company = %s '
            'GROUP BY m.origin',
            [utils.convert_to_reference(p) for p in contracts] +
            today_value + [company_id])
        for contract_id, sum in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(sum, Decimal):
                sum = Decimal(str(sum))
            res[int(contract_id.split(',')[1])] = sum
        return res

    def on_change_with_payment_lines(self, name=None):
        return map(lambda x: x.id, sorted(utils.get_domain_instances(self,
            'payment_lines'), key=lambda x: x.date, reverse=True))
