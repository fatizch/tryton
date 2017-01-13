# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model, utils
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementDefinition',
    'EndorsementPart',
    'EndorsementLoanField',
    'EndorsementLoanShareField',
    'EndorsementLoanIncrementField',
    'EndorsementContractLoanField',
    ]


class EndorsementDefinition:
    __name__ = 'endorsement.definition'

    is_loan = fields.Function(
        fields.Boolean('Is Loan'),
        'on_change_with_is_loan')

    @fields.depends('endorsement_parts')
    def on_change_with_is_loan(self, name=None):
        return any([x.kind == 'loan' for x in self.endorsement_parts])

    def get_rebill_end(self, contract_endorsement):
        contract = contract_endorsement.contract
        if not contract.is_loan or contract.status == 'void':
            return super(EndorsementDefinition, self).get_rebill_end(
                contract_endorsement)
        return max(contract_endorsement.contract.last_invoice_end or
            datetime.date.min, contract_endorsement.endorsement.effective_date,
            utils.today())


class EndorsementPart:
    __name__ = 'endorsement.part'

    loan_fields = fields.One2Many(
        'endorsement.loan.field', 'endorsement_part', 'Loan Fields', states={
            'invisible': Eval('kind', '') != 'loan'},
        depends=['kind'], delete_missing=True)
    loan_share_fields = fields.One2Many('endorsement.loan.share.field',
        'endorsement_part', 'Endorsement Loan Share Fields', states={
            'invisible': Eval('kind', '') != 'loan_share'},
        depends=['kind'], delete_missing=True)
    loan_increment_fields = fields.One2Many('endorsement.loan.increment.field',
        'endorsement_part', 'Endorsement Loan Increment Field', states={
            'invisible': Eval('kind', '') != 'loan'},
        depends=['kind'], delete_missing=True)

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(('loan', 'Loan'))
        cls.kind.selection.append(('loan_share', 'Loan Share'))

    @fields.depends('kind')
    def on_change_with_endorsed_model(self, name=None):
        if self.kind == 'loan':
            return Pool().get('ir.model').search([
                    ('model', '=', 'loan')])[0].id
        elif self.kind == 'loan_share':
            return Pool().get('ir.model').search([
                    ('model', '=', 'contract')])[0].id
        return super(EndorsementPart, self).on_change_with_endorsed_model(name)

    def clean_up(self, endorsement):
        if self.kind == 'loan':
            for field in self.loan_fields:
                endorsement.values.pop(field.name, None)
            if self.loan_increment_fields and endorsement.increments:
                Pool().get('endorsement.loan.increment').delete(
                    endorsement.increments)
        elif self.kind == 'loan_share':
            to_delete = []
            for covered_element in endorsement.covered_elements:
                for option in covered_element.options:
                    loan_shares = []
                    for loan_share in option.loan_shares:
                        for field in self.loan_share_fields:
                            if field.name in loan_share.values:
                                del loan_share.values[field.name]
                        if not loan_share.values:
                            to_delete.append(loan_share)
                        else:
                            loan_shares.append(loan_share)
                    option.loan_shares = loan_shares
            if to_delete:
                LoanShareEndorsement = Pool().get('endorsement.loan.share')
                LoanShareEndorsement.delete(to_delete)
        super(EndorsementPart, self).clean_up(endorsement)


class EndorsementLoanField(field_mixin('loan'), model.CoogSQL, model.CoogView):
    'Endorsement Loan Field'

    __name__ = 'endorsement.loan.field'


class EndorsementLoanShareField(field_mixin('loan.share'), model.CoogSQL,
        model.CoogView):
    'Endorsement Loan Share Field'

    __name__ = 'endorsement.loan.share.field'


class EndorsementLoanIncrementField(field_mixin('loan.increment'),
        model.CoogSQL, model.CoogView):
    'Endorsement Loan Increment Field'

    __name__ = 'endorsement.loan.increment.field'


class EndorsementContractLoanField(field_mixin('contract-loan'),
        model.CoogSQL, model.CoogView):
    'Endorsement Contract Loan Field'

    __name__ = 'endorsement.contract.loan.field'
