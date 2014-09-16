from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementPart',
    'EndorsementLoanField',
    ]


class EndorsementPart:
    __name__ = 'endorsement.part'

    loan_fields = fields.One2Many(
        'endorsement.loan.field', 'endorsement_part', 'Loan Fields', states={
            'invisible': Eval('kind', '') != 'loan'},
        depends=['kind'])

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(('loan', 'Loan'))

    def clean_up(self, endorsement):
        super(EndorsementPart, self).clean_up(endorsement)
        for field in self.loan_fields:
            endorsement.values.pop(field.name, None)


class EndorsementLoanField(field_mixin('loan'), model.CoopSQL, model.CoopView):
    'Endorsement Loan Field'

    __name__ = 'endorsement.loan.field'
