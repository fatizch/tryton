import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.coop_utils import fields, export

__metaclass__ = PoolMeta
__all__ = [
    'Party',
    ]


class Party:
    __name__ = 'party.party'

    suspense_account = fields.Property(fields.Many2One('account.account',
            'Suspense Account', domain=[
                ('kind', '=', 'other'),
                ('company', '=', Eval('context', {}).get('company')),
                ],
            states={
                'required': ~~(Eval('context', {}).get('company')),
                'invisible': ~Eval('context', {}).get('company'),
                }))

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.suspense_account = copy.copy(cls.suspense_account)
        cls.suspense_account.domain = export.clean_domain_for_import(
            cls.suspense_account.domain, 'company')
