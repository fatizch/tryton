# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields

__all__ = [
    'InsurerDelegation',
    ]


class InsurerDelegation:
    __metaclass__ = PoolMeta
    __name__ = 'insurer.delegation'

    claim_create_indemnifications = fields.Boolean('Indemnifications Creation')
    claim_pay_indemnifications = fields.Boolean('Indemnifications Payment')

    @classmethod
    def __setup__(cls):
        super(InsurerDelegation, cls).__setup__()
        cls._delegation_flags += ['claim_create_indemnifications',
            'claim_pay_indemnifications']

    @classmethod
    def default_claim_create_indemnifications(cls):
        return True

    @classmethod
    def default_claim_pay_indemnifications(cls):
        return True
