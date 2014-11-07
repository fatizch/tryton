from trytond.pool import PoolMeta, Pool
from trytond.modules.cog_utils import fields, model

__all__ = [
    'PlanLines',
    'PlanLinesCoverageRelation',
    'Commission',
    'Plan',
    'PlanRelation',
    ]
__metaclass__ = PoolMeta


class Commission:
    __name__ = 'commission'
    commissionned_contract = fields.Function(
        fields.Many2One('contract', 'Commissioned Contract'),
        'get_commissionned_contract')
    commissionned_option = fields.Function(
        fields.Many2One('contract.option', 'Commissioned Option'),
        'get_commissionned_option')

    def get_commissionned_option(self, name):
        if (self.origin and self.origin.details[0] and
                getattr(self.origin.details[0], 'option', None)):
            return self.origin.details[0].option.id

    def get_commissionned_contract(self, name):
        if (self.origin and self.origin.details[0] and
                getattr(self.origin.details[0], 'option', None)):
            return self.origin.details[0].option.parent_contract.id

    def _group_to_invoice_key(self):
        direction = {
            'in': 'out',
            'out': 'in',
            }.get(self.type_)
        document = 'invoice'
        return (('agent', self.agent),
            ('type', '%s_%s' % (direction, document)),
            )

    @classmethod
    def invoice(cls, commissions):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        invoices = super(Commission, cls).invoice(commissions)
        in_credit_note_invoice = [invoice for invoice in invoices
            if (invoice.total_amount < 0 and invoice.type == 'in_invoice')]
        out_credit_note_invoice = [invoice for invoice in invoices
            if (invoice.total_amount < 0 and invoice.type == 'out_invoice')]
        if in_credit_note_invoice:
            Invoice.write(in_credit_note_invoice, {'type': 'in_credit_note'})
        if out_credit_note_invoice:
            Invoice.write(in_credit_note_invoice, {'type': 'out_credit_note'})
        return invoices


class Plan:
    __name__ = 'commission.plan'

    plan_relation = fields.Many2Many('commission_plan-commission_plan',
        'from_', 'to', 'Plan Relation', size=1)
    reverse_plan_relation = fields.Many2Many('commission_plan-commission_plan',
        'to', 'from_', 'Reverse Plan Relation', size=1)

    @classmethod
    def get_context_formula(cls, amount, product, pattern=None):
        context = super(Plan, cls).get_context_formula(amount, product)
        context['names']['nb_years'] = (pattern or {}).get('nb_years', 0)
        return context

    def compute(self, amount, product, pattern=None):
        'Compute commission amount for the amount'
        if pattern is None:
            pattern = {}
        pattern['product'] = product.id if product else None
        context = self.get_context_formula(amount, product, pattern)
        for line in self.lines:
            if line.match(pattern):
                return line.get_amount(**context)


class PlanLines:
    __name__ = 'commission.plan.line'

    options = fields.Many2Many(
        'commission.plan.lines-offered.option.description', 'plan_line',
        'option', 'Options')
    options_extract = fields.Function(fields.Text('Options'),
        'get_options_extract')

    def match(self, pattern):
        if 'option' in pattern:
            return pattern['option'] in self.options

    def get_options_extract(self, name):
        return ' \n'.join((option.name for option in self.options))


class PlanLinesCoverageRelation(model.CoopSQL, model.CoopView):
    'Commission Plan Line - Offered Option Description'
    __name__ = 'commission.plan.lines-offered.option.description'

    plan_line = fields.Many2One('commission.plan.line', 'Plan Line',
        ondelete='CASCADE')
    option = fields.Many2One('offered.option.description', 'Option',
        ondelete='RESTRICT')


class PlanRelation(model.CoopSQL, model.CoopView):
    'Commission Plan - Commission Plan'
    __name__ = 'commission_plan-commission_plan'

    from_ = fields.Many2One('commission.plan', 'Plan')
    to = fields.Many2One('commission.plan', 'Plan')
