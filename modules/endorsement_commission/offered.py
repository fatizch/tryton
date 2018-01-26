# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import And, Eval

__metaclass__ = PoolMeta
__all__ = [
    'EndorsementPart',
    ]


class EndorsementPart:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.part'

    @classmethod
    def __setup__(cls):
        super(EndorsementPart, cls).__setup__()
        cls.kind.selection.append(
            ('commission', 'Commission'))
        cls.contract_fields.states['invisible'] = And(
            cls.contract_fields.states['invisible'],
            Eval('kind', '') != 'commission')
