from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import utils, fields

__metaclass__ = PoolMeta

__all__ = [
    'Clause',
    ]


class Clause:
    __name__ = 'clause'

    with_beneficiary_list = fields.Boolean('With beneficiary list',
        states={'invisible': (Eval('kind', '') != 'beneficiary')
                | Eval('may_be_overriden', False)})

    @classmethod
    def __setup__(cls):
        super(Clause, cls).__setup__()
        utils.update_selection(cls, 'kind', [('beneficiary', 'Beneficiary')])
        cls.may_be_overriden.states['invisible'] = Eval(
            'with_beneficiary_list', False)
        cls._error_messages.update({
                'may_not_override': 'It is not possible to allow overriding of'
                    ' clauses with beneficiary list',
                })

    @classmethod
    def validate(cls, clauses):
        for clause in clauses:
            if clause.with_beneficiary_list and clause.may_be_overriden:
                cls.raise_user_error('may_not_override')

    @fields.depends('may_be_overriden', 'with_beneficiary_list')
    def on_change_with_with_beneficiary_list(self):
        if self.may_be_overriden:
            return False
        return self.with_beneficiary_list

    @fields.depends('may_be_overriden', 'with_beneficiary_list')
    def on_change_with_may_be_overriden(self):
        if self.with_beneficiary_list:
            return False
        return self.may_be_overriden
