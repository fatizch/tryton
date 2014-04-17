from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval, Bool

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta

__all__ = [
    'ContractOption',
    'Beneficiary',
    ]


class ContractOption:
    __name__ = 'contract.option'

    with_beneficiary_clause = fields.Function(
        fields.Boolean('With Beneficiary Clause', states={'invisible': True}),
        'on_change_with_with_beneficiary_clause')
    beneficiary_clause = fields.Many2One('clause', 'Beneficiary Clause',
        domain=[('coverages', '=', Eval('coverage'))], states={
            'invisible': ~Eval('with_beneficiary_clause'),
            'required': Bool(Eval('with_beneficiary_clause')),
            }, depends=['coverage', 'with_beneficiary_clause'],
            ondelete='RESTRICT')
    customized_beneficiary_clause = fields.Text('Customized Beneficiary Clause',
        states={
            'invisible': ~Eval('with_beneficiary_clause')})
    beneficiaries = fields.One2Many('contract.option.beneficiary', 'option',
        'Beneficiaries', states={
            'invisible': ~Eval('with_beneficiary_clause')})

    @classmethod
    def __setup__(cls):
        super(ContractOption, cls).__setup__()
        cls._error_messages.update({
                'invalid_beneficiary_shares': 'Total share for clause %s is '
                'invalid',
                'mix_share_and_none': 'Either all share must be completed or '
                'none',
                })

    @classmethod
    def init_default_values_from_coverage(cls, coverage, product,
            item_desc=None, start_date=None, end_date=None):
        res = super(ContractOption, cls).init_default_values_from_coverage(
            coverage, product, item_desc, start_date, end_date)
        res['with_beneficiary_clause'] = len(coverage.beneficiaries_clauses)
        if coverage.default_beneficiary_clause:
            res['beneficiary_clause'] = coverage.default_beneficiary_clause.id
            res['customized_beneficiary_clause'] = \
                coverage.default_beneficiary_clause.content
        return res

    @fields.depends('coverage')
    def on_change_with_beneficiary_clause(self, name=None):
        if not self.coverage:
            return
        return self.coverage.default_beneficiary_clause.id

    @fields.depends('coverage')
    def on_change_with_with_beneficiary_clause(self, name=None):
        if not self.coverage:
            return False
        return len(self.coverage.beneficiaries_clauses)

    def check_beneficiaries(self):
        if not self.beneficiaries:
            return
        if None in [getattr(x, 'share', None) for x in self.beneficiaries]:
            if len([x.share for x in self.beneficiaries
                    if getattr(x, 'share', None)]):
                self.raise_user_error('mix_share_and_none')
            else:
                return
        if not(sum(x.share for x in self.beneficiaries)) == Decimal(1):
            self.raise_user_error('invalid_beneficiary_shares',
                (self.rec_name))

    @fields.depends('beneficiary_clause')
    def on_change_with_customized_beneficiary_clause(self):
        if not self.beneficiary_clause:
            return ''
        return self.beneficiary_clause.content

    @classmethod
    def validate(cls, options):
        super(ContractOption, cls).validate(options)
        for option in options:
            option.check_beneficiaries()


class Beneficiary(model.CoopSQL, model.CoopView):
    'Contract Beneficiary'

    __name__ = 'contract.option.beneficiary'

    option = fields.Many2One('contract.option', 'Option', required=True,
        ondelete='CASCADE')
    accepting = fields.Boolean('Accepting')
    party = fields.Many2One('party.party', 'Party', states={
            'invisible': ~Eval('accepting'),
            'required': Bool(Eval('accepting')),
            }, depends=['accepting'],
        ondelete='RESTRICT')
    address = fields.Many2One('party.address', 'Address',
        domain=[('party', '=', Eval('party'))], states={
            'invisible': ~Eval('accepting'),
            'required': Bool(Eval('accepting')),
            }, depends=['party', 'accepting'], ondelete='RESTRICT')
    reference = fields.Char('Reference', states={
            'invisible': Bool(Eval('accepting')),
            'required': ~Eval('accepting'),
            })
    share = fields.Numeric('Share', digits=(4, 4))
    description = fields.Function(
        fields.Char('Description'),
        'on_change_with_description')

    @fields.depends('party', 'reference')
    def on_change_with_description(self, name=None):
        if self.party:
            return self.party.rec_name
        else:
            return self.reference

    @fields.depends('accepting')
    def on_change_accepting(self):
        if not self.accepting:
            return {'party': None, 'address': None}
        return {'reference': ''}
