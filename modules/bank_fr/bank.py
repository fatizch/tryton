import re

from trytond.pool import PoolMeta
from trytond.model import fields

from trytond.modules.cog_utils import model

__metaclass__ = PoolMeta
__all__ = [
    'Bank',
    'Agency',
    ]


class Bank:
    __name__ = 'bank'

    agencies = fields.One2Many('bank.agency', 'bank', 'Agencies')

    @classmethod
    def search_rec_name(cls, name, clause):
        return ['OR',
            [('bic',) + tuple(clause[1:])],
            [('party.name',) + tuple(clause[1:])],
            [('agencies.bank_code',) + tuple(clause[1:])]
            ]


class Agency(model.CoopSQL, model.CoopView):
    'Agency'
    __name__ = 'bank.agency'

    bank = fields.Many2One('bank', 'Bank', required=True, ondelete='CASCADE')
    name = fields.Char('Name')
    bank_code = fields.Char('Bank Code', size=5)
    branch_code = fields.Char('Branch Code', size=5)

    @classmethod3ef0cb7bb7e1
    def __setup__(cls):
        super(Agency, cls).__setup__()
        cls._error_messages.update({
                'wrong_branch_code': 'The branch code %s must contain 5 '
                'numeric chars.',
                'wrong_bank_code': 'The bank code %s must contain 5 numeric '
                'chars.',
                })

    @classmethod
    def validate(cls, instances):
        super(Agency, cls).validate(instances)
        for agency in instances:
            if agency.bank_code and not re.match('[0-9]{5}', agency.bank_code):
                cls.raise_user_error('wrong_agency_code', agency.bank_code)
            if agency.branch_code and not re.match('[0-9]{5}',
                    agency.branch_code):
                cls.raise_user_error('wrong_branch_code', agency.branch_code)

    @fields.depends('bank_code')
    def on_change_bank_code(self):
        self.bank_code = self.bank_code.zfill(5)

    @fields.depends('branch_code')
    def on_change_branch_code(self):
        self.branch_code = self.branch_code.zfill(5)
