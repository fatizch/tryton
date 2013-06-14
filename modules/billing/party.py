import copy

from trytond.pool import PoolMeta
from trytond.modules.coop_utils import fields

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

        # Hack to remove constraints when importing
        # TODO : Be cleaner
        def remove_company(domain):
            to_remove = []
            for i, elem in enumerate(domain):
                if elem[0] == 'company' and elem[1] == '=':
                    to_remove.insert(0, i)
            for i in to_remove:
                domain.pop(i)

        cls.account_payable = copy.copy(cls.account_payable)
        remove_company(cls.account_payable.domain)
        cls.account_receivable = copy.copy(cls.account_receivable)
        remove_company(cls.account_receivable.domain)

    @classmethod
    def _import_single_link(
            cls, instance, field_name, field, field_value, created, relink,
            target_model, to_relink):
        res = super(Party, cls)._import_single_link(instance, field_name,
            field, field_value, created, relink, target_model, to_relink)
        if field_name in ('account_receivable', 'account_payable'):
            return True
        return res
