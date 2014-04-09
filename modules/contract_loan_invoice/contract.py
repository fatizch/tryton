from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'ContractOption',
    'LoanShare',
    'Premium',
    ]


class ContractOption:
    __name__ = 'contract.option'

    def get_invoice_lines(self, start, end):
        lines = super(ContractOption, self).get_invoice_lines(start, end)
        for loan_share in self.loan_shares:
            lines.extend(loan_share.get_invoice_lines(start, end))
        return lines


class LoanShare:
    __name__ = 'loan.share'

    premiums = fields.One2Many('contract.premium', 'loan_share', 'Premiums')

    def get_invoice_lines(self, start, end):
        lines = []
        for premium in self.premiums:
            lines.extend(premium.get_invoice_lines(start, end))
        return lines


class Premium:
    __name__ = 'contract.premium'

    loan_share = fields.Many2One('loan.share', 'Loan Share', select=True,
        ondelete='CASCADE')

    @classmethod
    def get_possible_parent_field(cls):
        result = super(Premium, cls).get_possible_parent_field()
        result.add('loan_share')
        return result

    def get_main_contract(self, name=None):
        if self.loan_share:
            return self.loan_share.option.parent_contract.id
        return super(Premium, self).get_main_contract(name)

    def calculate_rated_entity(self):
        rated_entity = super(Premium, self).calculate_rated_entity()
        if rated_entity:
            return rated_entity
        parent = self.get_parent()
        if parent.__name__ == 'loan.share':
            rated_entity = parent.option.coverage
        return rated_entity
