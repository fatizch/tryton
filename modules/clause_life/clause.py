from trytond.pool import PoolMeta
from trytond.pyson import Eval, Or

from trytond.modules.cog_utils import utils, fields

__metaclass__ = PoolMeta

__all__ = [
    'Clause',
    ]


class Clause:
    __name__ = 'clause'

    with_beneficiary_list = fields.Boolean('With beneficiary list',
        states={'invisible': Or(
                Eval('kind', '') != 'beneficiary',
                ~~Eval('may_be_overriden'))})

    @classmethod
    def __setup__(cls):
        super(Clause, cls).__setup__()
        utils.update_selection(cls, 'kind', [('beneficiary', 'Beneficiary')])
        cls._error_messages.update({
                'may_not_override': 'It is not possible to allow overriding of'
                    ' clauses with beneficiary list',
                })

    @classmethod
    def validate(cls, clauses):
        for clause in clauses:
            if clause.with_beneficiary_list and clause.may_be_overriden:
                cls.raise_user_error('may_not_override')
