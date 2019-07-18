# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

__all__ = [
    'APIIdentity',
    'APICore',
    ]


class APIIdentity(metaclass=PoolMeta):
    __name__ = 'ir.api.identity'

    def get_api_context(self):
        context = super().get_api_context()
        if self.user and self.user.dist_network:
            context['dist_network'] = self.user.dist_network.id
        return context


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _identity_context_output_schema(cls):
        schema = super()._identity_context_output_schema()
        schema['properties']['dist_network'] = {'type': 'integer'}
        return schema
