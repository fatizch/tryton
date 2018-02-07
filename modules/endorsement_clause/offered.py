# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coog_core import fields, model
from trytond.modules.endorsement.endorsement import field_mixin


__all__ = [
    'EndorsementPart',
    'EndorsementClauseField',
    ]


class EndorsementPart:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.part'

    clause_fields = fields.One2Many(
        'endorsement.contract.clause.field', 'endorsement_part',
        'Clause Fields', states={
            'invisible': Eval('kind', '') != 'contract'}, depends=['kind'],
        delete_missing=True)


class EndorsementClauseField(field_mixin('contract.clause'),
        model.CoogSQL, model.CoogView):
    'Endorsement Clause Field'

    __name__ = 'endorsement.contract.clause.field'
