from decimal import Decimal
from simpleeval import simple_eval
from sql import Column, Null
from sql.operators import Or
from sql.aggregate import Sum

from trytond.tools import decistmt
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, If

from trytond.modules.commission import Commission as TrytonCommission
from trytond.modules.cog_utils import fields, utils

__metaclass__ = PoolMeta
__all__ = [
    'PlanLines',
    'Commission',
    'Plan',
    'Agent',
    ]


class Commission:
    __name__ = 'commission'

    is_prepayment = fields.Boolean('Is Prepayment',
        states=TrytonCommission._readonly_states,
        depends=TrytonCommission._readonly_depends)
    redeemed_prepayment = fields.Numeric('Redeemed Prepayment', digits=(16, 4),
        states=TrytonCommission._readonly_states,
        depends=TrytonCommission._readonly_depends)

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.amount.depends = ['redeemed_prepayment']
        cls.amount.domain = [If(~Eval('redeemed_prepayment'),
                ('amount', '!=', 0),
                (),
                )]
        cls._error_messages.update({
                'prepayment_amortization': 'Prepayment Amortization',
                'prepayment': 'Prepayment',
                })

    @classmethod
    def _get_origin(cls):
        models = super(Commission, cls)._get_origin()
        return models + ['contract.option']

    def _group_to_invoice_line_key(self):
        key = super(Commission, self)._group_to_invoice_line_key()
        with_prepayment = bool(self.redeemed_prepayment)
        return key + (('is_prepayment', self.is_prepayment),
            ('with_prepayment', with_prepayment))

    @classmethod
    def _get_invoice_line(cls, key, invoice, commissions):
        invoice_line = super(Commission, cls)._get_invoice_line(key, invoice,
            commissions)
        if invoice_line and key['is_prepayment']:
            invoice_line.description = cls.raise_user_error(
                    'prepayment', raise_exception=False)
        elif invoice_line and key['with_prepayment']:
            invoice_line.description = cls.raise_user_error(
                    'prepayment_amortization', raise_exception=False)
        return invoice_line

    def _group_to_agent_option_key(self):
        return (('agent', self.agent), ('option', self.commissioned_option))

    @classmethod
    def copy(cls, commissions, default=None):
        clones = super(Commission, cls).copy(commissions, default=default)
        if not Transaction().context.get('cancel_invoices', False):
            return clones
        for commission in clones:
            if commission.redeemed_prepayment:
                commission.redeemed_prepayment = \
                    -commission.redeemed_prepayment
        return clones


class PlanLines:
    __name__ = 'commission.plan.line'

    prepayment_formula = fields.Char('Prepayment Formula',
        help=('Python expression that will be evaluated with:\n'
            '- amount: the original amount'))

    def get_prepayment_amount(self, **context):
        """Return prepayment amount (as Decimal)"""
        if not self.prepayment_formula:
            return
        context.setdefault('functions', {})['Decimal'] = Decimal
        return simple_eval(decistmt(self.prepayment_formula), **context)


class Plan:
    __name__ = 'commission.plan'

    adjust_prepayment = fields.Boolean('Adjust Prepayment')

    def get_context_formula(self, amount, product, pattern=None):
        context = super(Plan, self).get_context_formula(amount, product,
            pattern)
        context['names']['first_year_premium'] = \
            (pattern or {}).get('first_year_premium', 0)
        return context

    def compute_prepayment(self, product, pattern=None):
        """Compute prepayment commission for the amount"""
        if pattern is None:
            pattern = {}
        pattern['product'] = product.id if product else None
        amount = 0
        context = self.get_context_formula(amount, product, pattern)
        for line in self.lines:
            if line.match(pattern):
                return line.get_prepayment_amount(**context)

    def compute_prepayment_schedule(self, option, agent):
        ''' Return a list of tuple with date and percentage'''
        today = utils.today()
        payment_date = option.parent_contract.signature_date or today
        return [(max(payment_date, today), 1)]


class Agent:
    __name__ = 'commission.agent'

    @classmethod
    def paid_prepayments(cls, agents):
        """
            agents is a list of tuple (agent_id, coverage_id)
            Return a dictionnary with (agent_id, coverage) as key
                and paid prepayment as value
        """
        pool = Pool()
        Commission = pool.get('commission')
        commission = Commission.__table__()

        result = {}
        if not agents:
            return result

        cursor = Transaction().cursor
        agent_column = Column(commission, 'agent')
        origin_column = Column(commission, 'origin')
        prepayment_column = Column(commission, 'is_prepayment')
        invoice_line = Column(commission, 'invoice_line')

        where_clause = Or()
        for agent in agents:
            where_clause.append(((agent_column == agent[0]) &
                    (prepayment_column == True) &
                    (origin_column == 'contract.option,' + str(agent[1])) &
                    (invoice_line != None)))
        cursor.execute(*commission.select(commission.agent, commission.origin,
                Sum(commission.amount),
                where=where_clause,
                group_by=[commission.agent, commission.origin]))
        for agent, option, amount in cursor.fetchall():
            result[(agent, option)] = amount

        return result

    @classmethod
    def outstanding_prepayment(cls, agents):
        """
            agents is a list of tuple (agent_id, coverage_id)
            Return a dictionnary with (agent, coverage) as key
                and outstanding amount as value
        """
        pool = Pool()
        Commission = pool.get('commission')
        commission = Commission.__table__()

        cursor = Transaction().cursor
        agent_column = Column(commission, 'agent')
        option_column = Column(commission, 'commissioned_option')
        origin_column = Column(commission, 'origin')
        prepayment_column = Column(commission, 'is_prepayment')
        reedemed_column = Column(commission, 'redeemed_prepayment')
        where_redeemed = Or()
        where_prepayment = Or()
        for agent in agents:
            where_redeemed.append(((agent_column == agent[0]) &
                    (reedemed_column != Null) &
                    (option_column == agent[1])))
            where_prepayment.append(((agent_column == agent[0]) &
                    (prepayment_column == True) &
                    (origin_column == 'contract.option,' + str(agent[1]))))

        result = {}

        # sum of redeemed prepayment
        cursor.execute(*commission.select(commission.agent,
                commission.commissioned_option,
                Sum(commission.redeemed_prepayment),
                where=where_redeemed,
                group_by=[commission.agent, commission.commissioned_option]))
        for agent, option, amount in cursor.fetchall():
            result[(agent, option)] = -amount

        # sum of prepayment
        cursor.execute(*commission.select(commission.agent, commission.origin,
                Sum(commission.amount),
                where=where_prepayment,
                group_by=[commission.agent, commission.origin]))
        for agent, option, amount in cursor.fetchall():
            option_id = int(option.split(',')[1])
            if (agent, option_id) in result:
                result[(agent, option_id)] += amount
            else:
                result[(agent, option_id)] = amount
        return result
