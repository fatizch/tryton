# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model

__all__ = [
    'OptionDescription',
    'OptionDescriptionBeneficiaryClauseRelation',
    ]


class OptionDescription(metaclass=PoolMeta):
    __name__ = 'offered.option.description'

    beneficiaries_clauses = fields.Many2Many(
        'offered.option.description-beneficiary_clause', 'coverage', 'clause',
        'Beneficiaries Clauses', help='Beneficiaries clauses available when '
        'subscribing this option',
        domain=[('kind', '=', 'beneficiary')])
    default_beneficiary_clause = fields.Many2One('clause', 'Default Clause',
        help='Beneficiaries default clause used when initializing the '
        'subscription',
        domain=[('id', 'in', Eval('beneficiaries_clauses'))],
        depends=['beneficiaries_clauses'], ondelete='RESTRICT')


class OptionDescriptionBeneficiaryClauseRelation(model.CoogSQL):
    'Relation Option Description To Beneficiary Clause'
    __name__ = 'offered.option.description-beneficiary_clause'

    coverage = fields.Many2One('offered.option.description', 'Coverage',
        ondelete='CASCADE')
    clause = fields.Many2One('clause', 'Clause', ondelete='RESTRICT')
