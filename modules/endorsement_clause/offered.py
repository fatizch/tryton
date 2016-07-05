# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields, model
from trytond.modules.endorsement import field_mixin


__metaclass__ = PoolMeta
__all__ = [
    'EndorsementPart',
    'EndorsementClauseField',
    ]


class EndorsementPart:
    __name__ = 'endorsement.part'

    clause_fields = fields.One2Many(
        'endorsement.contract.clause.field', 'endorsement_part',
        'Clause Fields', states={
            'invisible': Eval('kind', '') != 'contract'}, depends=['kind'],
        delete_missing=True)


class EndorsementClauseField(field_mixin('contract.clause'),
        model.CoopSQL, model.CoopView):
    'Endorsement Clause Field'

    __name__ = 'endorsement.contract.clause.field'
