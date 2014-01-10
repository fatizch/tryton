from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Configuration',
    'Payment',
    ]


class Configuration:
    __name__ = 'account.configuration'

    default_suspense_account = fields.Function(
        fields.Many2One('account.account', 'Default Suspense Account', domain=[
                ('kind', '=', 'other'),
                ('company', '=', Eval('context', {}).get('company')),
                ]),
        'get_account', setter='set_account')
    cash_account = fields.Property(
        fields.Many2One('account.account', 'Cash Account',
            domain=[('kind', '=', 'revenue')]))
    check_account = fields.Property(
        fields.Many2One('account.account', 'Check Account',
            domain=[('kind', '=', 'revenue')]))
    collection_journal = fields.Property(
        fields.Many2One('account.journal', 'Journal', domain=[
                ('type', '=', 'cash')]))

    @classmethod
    def _export_must_export_field(cls, field_name, field):
        # Function field are not exported by default
        if field_name == 'default_suspense_account':
            return True
        return super(Configuration, cls)._export_must_export_field(
            field_name, field)

    def _export_override_default_suspense_account(self, exported, result,
            my_key):
        return self._export_default_account('default_suspense_account',
            exported, result, my_key)


class Payment:
    __name__ = 'account.payment'

    collection = fields.Many2One('collection', 'Collection')
