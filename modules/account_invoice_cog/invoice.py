from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import export, fields
from trytond.modules.report_engine import Printable

__metaclass__ = PoolMeta
__all__ = [
    'Invoice',
    ]


class Invoice(export.ExportImportMixin, Printable):
    __name__ = 'account.invoice'
    _func_key = 'number'

    icon = fields.Function(
        fields.Char('Icon'),
        'on_change_with_icon')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.move.select = True
        cls.cancel_move.select = True
        cls.cancel_move.states['invisible'] = ~Eval('cancel_move')

    @classmethod
    def is_master_object(cls):
        return True

    @fields.depends('state', 'amount_to_pay_today')
    def on_change_with_icon(self, name=None):
        if self.state == 'cancel':
            return 'invoice_cancel'
        elif self.state == 'paid':
            return 'invoice_paid'
        elif self.state == 'draft':
            return 'invoice_draft'
        elif self.amount_to_pay_today > 0:
            return 'invoice_unpaid'
        elif self.state == 'posted':
            return 'invoice_post'
        else:
            return 'invoice'

    def get_lang(self):
        return self.party.lang.code

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.company.party
