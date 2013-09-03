import copy

from trytond.pool import PoolMeta
from trytond.modules.coop_utils import fields, export

__all__ = [
    'Party',
]


class Party():
    'Party'

    __metaclass__ = PoolMeta
    __name__ = 'party.party'

    receivable_lines = fields.One2ManyDomain('account.move.line', 'party',
        'Receivable Lines', domain=[('account.kind', '=', 'receivable'),
            ('reconciliation', '=', None)], loading='lazy')
    payable_lines = fields.One2ManyDomain('account.move.line', 'party',
        'Payable Lines', domain=[('account.kind', '=', 'payable'),
            ('reconciliation', '=', None)], loading='lazy')

    @classmethod
    def __setup__(cls):
        super(Party, cls).__setup__()
        cls.account_payable = copy.copy(cls.account_payable)
        cls.account_payable.domain = export.clean_domain_for_import(
            cls.account_payable.domain, 'company')
        cls.account_receivable = copy.copy(cls.account_receivable)
        cls.account_receivable.domain = export.clean_domain_for_import(
            cls.account_receivable.domain, 'company')

    @classmethod
    def _export_skips(cls):
        result = super(Party, cls)._export_skips()
        result.add('receivable_lines')
        result.add('payable_lines')
        return result

    @classmethod
    def _import_single_link(
            cls, instance, field_name, field, field_value, created, relink,
            target_model, to_relink):
        res = super(Party, cls)._import_single_link(instance, field_name,
            field, field_value, created, relink, target_model, to_relink)
        if field_name in ('account_receivable', 'account_payable'):
            return True
        return res
