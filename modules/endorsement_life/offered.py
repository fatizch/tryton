# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementPart',
    'EndorsementBeneficiaryField',
    ]


class EndorsementPart:
    __name__ = 'endorsement.part'

    beneficiary_fields = fields.One2Many(
        'endorsement.contract.beneficiary.field', 'endorsement_part',
        'Beneficiary Fields', states={
            'invisible': Eval('kind', '') != 'option'}, depends=['kind'],
        delete_missing=True)

    def clean_up(self, endorsement):
        if self.kind == 'option':
            to_delete = []
            for covered_element in endorsement.covered_elements:
                for option in covered_element.options:
                    beneficiaries = []
                    for beneficiary in option.beneficiaries:
                        for field in self.beneficiary_fields:
                            if field.name in beneficiary.values:
                                del beneficiary.values[field.name]
                        if not beneficiary.values:
                            to_delete.append(beneficiary)
                        else:
                            beneficiaries.append(beneficiary)
                    option.beneficiaries = beneficiaries
            if to_delete:
                BeneficiaryEndorsement = Pool().get(
                    'endorsement.contract.beneficiary')
                BeneficiaryEndorsement.delete(to_delete)
        super(EndorsementPart, self).clean_up(endorsement)


class EndorsementBeneficiaryField(field_mixin('contract.option.beneficiary'),
        model.CoopSQL, model.CoopView):
    'Endorsement Beneficiary Field'

    __name__ = 'endorsement.contract.beneficiary.field'
