import copy
from decimal import Decimal

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model

__metaclass__ = PoolMeta

__all__ = [
    'Beneficiary',
    'ContractClause',
    'CoveredData',
    ]


class Beneficiary(model.CoopSQL, model.CoopView):
    'Contract Beneficiary'

    __name__ = 'contract.clause.beneficiary'

    accepting = fields.Boolean('Accepting')
    clause = fields.Many2One('contract.clause', 'Clause', required=True,
        ondelete='RESTRICT')
    party = fields.Many2One('party.party', 'Party', states={
            'required': Eval('accepting', False)}, depends=['accepting'],
        ondelete='RESTRICT')
    details = fields.Text('Details', states={'invisible': ~~Eval('accepting')})
    share = fields.Numeric('Share', digits=(4, 4), required=True)
    description = fields.Function(
        fields.Char('Description'),
        'on_change_with_description')

    @fields.depends('party', 'details')
    def on_change_with_description(self, name=None):
        if self.party:
            return self.party.rec_name
        return self.details.splitlines().join(' ')

    @classmethod
    def default_share(cls):
        return Decimal('1')


class ContractClause:
    __name__ = 'contract.clause'

    beneficiaries = fields.One2Many('contract.clause.beneficiary', 'clause',
        'Beneficiaries', states={'invisible': ~Eval('with_beneficiary_list')},
        depends=['with_beneficiary_list'])
    with_beneficiary_list = fields.Function(
        fields.Boolean('With Beneficiay list', states={'invisible': True}),
        'on_change_with_with_beneficiary_list')

    @classmethod
    def __setup__(cls):
        super(ContractClause, cls).__setup__()
        cls._error_messages.update({
                'invalid_beneficiary_shares': 'Total share for clause %s is'
                'invalid',
                })

    @fields.depends('clause')
    def on_change_with_with_beneficiary_list(self, name=None):
        if not self.clause:
            return False
        return self.clause.with_beneficiary_list

    @classmethod
    def validate(cls, clauses):
        for clause in clauses:
            if not clause.with_beneficiary_list:
                continue
            if not clause.beneficiaries:
                return
            if not(sum((x.share for x in clause.beneficiaries)) ==
                    Decimal('1')):
                cls.raise_user_error('invalid_beneficiary_shares',
                    (clause.rec_name))


class CoveredData:
    __name__ = 'contract.covered_data'

    beneficiary_clauses = fields.One2ManyDomain('contract.clause',
        'covered_data', 'Beneficiary clauses', domain=[
            ('clause.kind', '=', 'beneficiary')])

    @classmethod
    def __setup__(cls):
        super(CoveredData, cls).__setup__()
        cls.clauses = copy.copy(cls.clauses)
        cls.clauses = fields.One2ManyDomain.init_from_One2Many(cls.clauses)
        cls.clauses.domain = [('clause.kind', '!=', 'beneficiary')]

    def init_clauses(self, option):
        super(CoveredData, self).init_clauses(option)
        self.beneficiary_clauses = []
        new_clauses = []
        for elem in self.clauses:
            if elem.clause.kind == 'beneficiary':
                self.beneficiary_clauses.append(elem)
            else:
                new_clauses.append(elem)
        self.clauses = new_clauses
        return new_clauses
