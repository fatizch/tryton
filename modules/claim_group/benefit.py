# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'Benefit',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    is_group = fields.Boolean('Group Benefit')

    @classmethod
    def __setup__(cls):
        super(Benefit, cls).__setup__()
        cls._error_messages.update({
                'subscriber_then_covered_enum': 'Subscriber then Covered',
                })

    @classmethod
    def get_beneficiary_kind(cls):
        return super(Benefit, cls).get_beneficiary_kind() + [
            ('subscriber_then_covered', cls.raise_user_error(
                    'subscriber_then_covered_enum', raise_exception=False)),
            ]
