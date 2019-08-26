# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from decimal import Decimal
from simpleeval import simple_eval
from sql import Column, Null, Literal
from sql.operators import Or
from sql.aggregate import Sum
from sql.conditionals import Case, Coalesce

from trytond.i18n import gettext
from trytond.tools import decistmt
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval, If, PYSONEncoder

from trytond.modules.coog_core import fields, utils

from trytond.modules.commission_insurance.commission import \
    COMMISSION_AMOUNT_DIGITS
from trytond.modules.commission_insurance.contract import \
    ANNUAL_CONVERSION_TABLE

__all__ = [
    'PlanLines',
    'Commission',
    'Plan',
    'Agent',
    'FilterCommissions',
    'FilterAggregatedCommissions',
    'AggregatedCommission',
    'CommissionDescriptionConfiguration',
    ]


class Commission(metaclass=PoolMeta):
    __name__ = 'commission'

    is_prepayment = fields.Boolean('Is Prepayment', readonly=True)
    redeemed_prepayment = fields.Numeric('Redeemed Prepayment',
        digits=(16, COMMISSION_AMOUNT_DIGITS), readonly=True)

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls.amount.depends = ['redeemed_prepayment']
        cls.amount.domain = [If(~Eval('redeemed_prepayment'),
                ('amount', '!=', 0),
                (),
                )]

    @classmethod
    def _get_origin(cls):
        models = super(Commission, cls)._get_origin()
        return models + ['contract.option']

    def _group_to_invoice_line_key(self):
        key = super(Commission, self)._group_to_invoice_line_key()
        with_prepayment = bool(self.redeemed_prepayment and not self.amount)
        return key + (('is_prepayment', self.is_prepayment),
            ('with_prepayment', with_prepayment))

    @classmethod
    def _get_invoice_line(cls, key, invoice, commissions):
        invoice_line = super(Commission, cls)._get_invoice_line(key, invoice,
            commissions)
        if invoice_line and key['is_prepayment']:
            invoice_line.description = gettext(
                'commission_insurance_prepayment.msg_prepayment')
        elif invoice_line and key['with_prepayment']:
            invoice_line.description = gettext(
                'commission_insurance_prepayment.msg_prepayment_amortization')
        return invoice_line

    def _group_to_agent_option_key(self):
        return (('agent', self.agent), ('option',
                getattr(self, 'commissioned_option', None)))

    def get_base_amount(self, name):
        base_amount = super(Commission, self).get_base_amount(name)
        if self.redeemed_prepayment and self.commission_rate:
            base_amount += self.redeemed_prepayment / self.commission_rate
        return base_amount.quantize(Decimal(10) ** -COMMISSION_AMOUNT_DIGITS)

    def update_new_commission_after_cancel(self):
        super(Commission, self).update_new_commission_after_cancel()
        if self.redeemed_prepayment:
            self.redeemed_prepayment *= -1

    def update_cancel_copy(self):
        super(Commission, self).update_cancel_copy()
        if self.redeemed_prepayment:
            self.redeemed_prepayment *= -1

    def getter_calculation_description(self, name):
        if self.amount == 0 and self.redeemed_prepayment:
            return ''
        description = super().getter_calculation_description(name)
        details = self.extra_details or {}
        if self.is_prepayment and details:
            commission_title = ''
            desc_configuration = Pool().get(
                'commission.description.configuration').get_singleton()
            if details.get('is_adjustment', False):
                if (desc_configuration and desc_configuration.
                        prepayment_adjustment_commission_title):
                    commission_title = desc_configuration. \
                        prepayment_adjustment_commission_title
                description += commission_title
                description += '\n%s = %s * %s' % (
                    str(self.amount) if self.amount is not None else '',
                    str(details.get('prepayment_amount', Decimal(0))),
                    str(details.get('duration_factor', Decimal(1))))
            else:
                if (desc_configuration
                        and desc_configuration.prepayment_commission_title):
                    commission_title = desc_configuration. \
                        prepayment_commission_title
                nb_units = Decimal(12)
                if (self.commissioned_option.coverage.premium_rules[0].
                        frequency in ANNUAL_CONVERSION_TABLE):
                    nb_units = ANNUAL_CONVERSION_TABLE[
                        self.commissioned_option.coverage.premium_rules[0].
                        frequency]
                description += commission_title
                description += '\n%s = %s' % (str(self.amount)
                    if self.amount is not None else '',
                    str((self.base_amount or Decimal(0)) / nb_units))
                if details.get('rate', self.commission_rate):
                    description += ' * %s' % str(details.get('rate',
                            self.commission_rate))
                if details.get('percentage'):
                    description += ' * %s' % str(details.get('percentage'))
                description += ' * %s' % str(nb_units)
        elif details.get('type', '') == 'linear':
            redeemed_amount = self.redeemed_prepayment or Decimal('0.0')
            if redeemed_amount <= Decimal('0.001'):
                redeemed_amount = Decimal('0.0')
            if redeemed_amount != 0:
                description = (gettext(
                        'commission_insurance_prepayment'
                        '.msg_redeemed_prepayment',
                        redeemed_amount=redeemed_amount)
                    + '\n' + description)
                description += ' - %s' % redeemed_amount
        return description


class PlanLines(metaclass=PoolMeta):
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

    def get_formula_description(self, name):
        lines = [super(PlanLines, self).get_formula_description(name)]
        if self.prepayment_formula:
            lines.append(self.prepayment_formula)
        return ' \n'.join(lines)


class Plan(metaclass=PoolMeta):
    __name__ = 'commission.plan'

    is_prepayment = fields.Function(fields.Boolean('Is Prepayment'),
        'getter_is_prepayment', setter='setter_void',
        searcher='search_is_prepayment')
    adjust_prepayment = fields.Boolean('Adjust Prepayment')
    delete_unpaid_prepayment = fields.Boolean('Delete Unpaid Prepayment',
        help='Redeemed of unpaid invoices will be deleted once contracts '
        'are terminated')
    prepayment_due_at_first_paid_invoice = fields.Boolean('Prepayment Due'
        ' At First Paid Invoice', help='The prepayment is due only when'
        ' a contract has at least one paid invoice',
        states={'invisible': ~Eval('is_prepayment')},
        depends=['is_prepayment'])

    @classmethod
    def view_attributes(cls):
        return super(Plan, cls).view_attributes() + [
            (
                "/form/notebook/page[@name='is_prepayment']",
                'states',
                {'invisible': ~Eval('is_prepayment')}
                ),
            ]

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
        return [(max(payment_date, today), Decimal(1))]

    def getter_is_prepayment(self, name):
        # TODO: Merge module with commission_insurance_prepayment_rule_engine
        # This method is overrided into the module
        # commission_insurance_prepayment_rule_engine
        return False

    @classmethod
    def search_is_prepayment(cls, name, clause):
        # TODO: Merge module with commission_insurance_prepayment_rule_engine
        # This method is overrided into the module
        # commission_insurance_prepayment_rule_engine
        return []


class Agent(metaclass=PoolMeta):
    __name__ = 'commission.agent'

    @classmethod
    def _prepayment_base_amount_sum_column(cls, commission):
        return Sum(Case(
                (Coalesce(commission.commission_rate, 0) == 0, 0),
                else_=((Coalesce(commission.amount, 0) +
                    Coalesce(commission.redeemed_prepayment, 0)) /
                    commission.commission_rate)
                ))

    @classmethod
    def sum_of_prepayments(cls, agents):
        """
            Agents is a list of tuple (agent_id, coverage_id)
            Return a dictionnary with (agent_id, coverage) as key
                and [prepayments, base_amount] as value
        """
        pool = Pool()
        Commission = pool.get('commission')
        commission = Commission.__table__()

        result = {}
        if not agents:
            return result

        cursor = Transaction().connection.cursor()
        agent_column = Column(commission, 'agent')
        option_column = Column(commission, 'commissioned_option')
        prepayment_column = Column(commission, 'is_prepayment')

        where_clause = Or()
        for agent in agents:
            where_clause.append(((agent_column == agent[0]) &
                    (prepayment_column == True) &  # NOQA
                    (option_column == agent[1])))
        # base_amount is computed for each line depending on what it contains.
        # if there is no rate or it is equal to 0, base amount is equal to 0
        # if there is a redeemed prepayment, it should be taken into account
        cursor.execute(*commission.select(commission.agent, commission.origin,
                Sum(commission.amount),
                cls._prepayment_base_amount_sum_column(commission),
                where=where_clause,
                group_by=[commission.agent, commission.origin]))
        for agent, option, amount, base_amount in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
            if not isinstance(base_amount, Decimal):
                base_amount = Decimal(str(base_amount))
            result[(agent, int(option.split(',')[1]))] = [amount, base_amount]
        return result

    @classmethod
    def sum_of_redeemed_prepayment(cls, agents):
        """
            Agents is a list of tuple (agent_id, option_id)
            Return a dictionnary with (agent_id, option_id) as key
                and [sum of redeemed amount, sum of base amount] as value
        """
        pool = Pool()
        Commission = pool.get('commission')
        commission = Commission.__table__()

        cursor = Transaction().connection.cursor()
        agent_column = Column(commission, 'agent')
        option_column = Column(commission, 'commissioned_option')
        redeemed_column = Column(commission, 'redeemed_prepayment')
        where_redeemed = Or()

        result = {}
        if not agents:
            return result

        for agent in agents:
            where_redeemed.append(((agent_column == agent[0]) &
                    (redeemed_column != Null) &
                    (option_column == agent[1])))
        # base_amount is computed for each line depending on what it contains.
        # if there is no rate or it is equal to 0, base amount is equal to 0
        # if there is a prepayment amount, it should be taken into account
        cursor.execute(*commission.select(commission.agent,
                commission.commissioned_option,
                Sum(commission.redeemed_prepayment),
                cls._prepayment_base_amount_sum_column(commission),
                where=where_redeemed,
                group_by=[commission.agent, commission.commissioned_option]))
        for agent, option, amount, base_amount in cursor.fetchall():
            # SQLite uses float for SUM
            if not isinstance(amount, Decimal):
                amount = Decimal(str(amount))
            if not isinstance(base_amount, Decimal):
                base_amount = Decimal(str(base_amount))
            result[(agent, option)] = [amount, base_amount]
        return result

    @classmethod
    def outstanding_prepayment(cls, agents):
        """
            Agents is a list of tuple (agent_id, option_id)
            Return a dictionnary with (agent_id, option_id) as key
            and [outstanding amount, outstanding_base_amount, details] as value
        """
        result = cls.sum_of_prepayments(agents)
        redeemed_prepayments = cls.sum_of_redeemed_prepayment(agents)
        for key in result:
            result[key].append({'sum_of_prepayments': result[key][0]})
        for key, prepayment_amount_base in redeemed_prepayments.items():
            if key not in result:
                continue
            result[key][2]['sum_of_redeemed_prepayments'] = \
                prepayment_amount_base[0]
            result[key][0] -= prepayment_amount_base[0]
            result[key][1] -= prepayment_amount_base[1]
        return result


class FilterCommissions(metaclass=PoolMeta):
    __name__ = 'commission.filter_commission'

    def do_aggregated_commissions(self, action):
        act, ctx = super(
            FilterCommissions, self).do_aggregated_commissions(action)
        transaction = Transaction()
        active_model = transaction.context.get('active_model')
        active_id = transaction.context.get('active_id')
        if active_model == 'contract':
            contract = Pool().get('contract')(active_id)
            options = contract.options + contract.covered_element_options
            if 'extra_context' not in ctx:
                ctx['extra_context'] = {}
            if 'origins' not in ctx['extra_context']:
                ctx['extra_context']['origins'] = []
            ctx['extra_context']['origins'].extend(
                [str(o) for o in options])
        return act, ctx


class FilterAggregatedCommissions(metaclass=PoolMeta):
    __name__ = 'commission.aggregated.open_detail'

    def do_filter_commission(self, action):
        context = Transaction().context
        commission = Pool().get('commission')(
            context.get('active_id'))
        if commission.origin.__name__ != 'contract.option':
            return super(FilterAggregatedCommissions,
                self).do_filter_commission(action)
        clause = [('origin', '=', str(commission.origin))]
        clause += [('agent', '=', commission.agent.id)]
        if commission.is_prepayment:
            clause += [('date', '=', commission.date)]
        action.update({'pyson_domain': PYSONEncoder().encode(clause)})
        return action, {}


class AggregatedCommission(metaclass=PoolMeta):

    __name__ = 'commission.aggregated'

    @classmethod
    def get_group_by(cls, tables):
        commission = tables['commission']
        group_by = super(AggregatedCommission, cls).get_group_by(tables)
        return group_by + [
            Case((commission.is_prepayment == Literal(False), Null),
                else_=commission.date), commission.is_prepayment
            ]


class CommissionDescriptionConfiguration(metaclass=PoolMeta):

    __name__ = 'commission.description.configuration'

    prepayment_commission_title = fields.Char(
        'Prepayment Commission Title', help='Contains the string which '
        'will  be used to introduce prepayment commissions calculation details',
        required=True, translate=True)
    prepayment_adjustment_commission_title = fields.Char(
        'Prepayment Adjustment Commission Title', help='Contains the '
        'string which will be used to introduce prepayment adjustment'
        'commissions calculation details', required=True, translate=True)
