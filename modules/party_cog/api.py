# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields


__all__ = [
    'APIIdentity',
    'Party',
    'APICore',
    ]


class APIIdentity(metaclass=PoolMeta):
    __name__ = 'ir.api.identity'

    party = fields.Many2One('party.party', 'Party', ondelete='CASCADE',
        select=True, help='If set, the identity will be bound to this party, '
        'which will limit what may be available in consultation APIs')

    def get_api_context(self):
        context = super().get_api_context()
        context['party'] = self.party.id if self.party else None
        return context


class Party(metaclass=PoolMeta):
    __name__ = 'party.party'

    identities = fields.One2Many('ir.api.identity', 'party', 'Identities',
        delete_missing=True, target_not_required=True,
        help='The list of identities which will be associated to this party')


class APICore(metaclass=PoolMeta):
    __name__ = 'api.core'

    @classmethod
    def _identity_context_output_schema(cls):
        schema = super()._identity_context_output_schema()
        schema['properties']['party'] = {'type': ['null', 'integer']}
        schema['required'].append('party')
        return schema

    @classmethod
    def _identity_context_examples(cls):
        examples = super()._identity_context_examples()
        for example in examples:
            example['output']['party'] = None
        examples.append({
                'input': {'kind': 'generic', 'identifier': '425341'},
                'output': {'user': 3, 'party': 20},
                })
        return examples
