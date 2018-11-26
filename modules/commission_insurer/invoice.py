# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval, Bool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils


__all__ = [
    'Invoice',
    ]


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    insurer_role = fields.Many2One('insurer', 'Insurer', ondelete='RESTRICT',
        readonly=True, states={
            'invisible': ~Eval('is_for_insurer'),
            'required': Bool(Eval('is_for_insurer')),
            }, depends=['is_for_insurer'])
    is_for_insurer = fields.Function(
        fields.Boolean('For insurer'), 'on_change_with_is_for_insurer')

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection += [
            ('all_insurer_invoices', 'All Insurer Invoices'),
            ]

    @classmethod
    def __register__(cls, module_name):
        TableHandler = backend.get('TableHandler')
        cursor = Transaction().connection.cursor()
        handler = TableHandler(cls, module_name)
        to_migrate = not handler.column_exist('insurer_role')

        super(Invoice, cls).__register__(module_name)

        # Migration from 1.10 : Store insurer
        if to_migrate:
            pool = Pool()
            to_update = cls.__table__()
            insurer = pool.get('insurer').__table__()
            party = pool.get('party.party').__table__()
            update_data = party.join(insurer, condition=(
                    insurer.party == party.id)
                ).select(insurer.id.as_('insurer_id'), party.id)
            cursor.execute(*to_update.update(
                    columns=[to_update.insurer_role],
                    values=[update_data.insurer_id],
                    from_=[update_data],
                    where=update_data.id == to_update.party))

    @fields.depends('party')
    def on_change_with_is_for_insurer(self, name=None):
        return self.party.is_insurer if self.party else False

    @classmethod
    def get_commission_insurer_invoice_types(cls):
        return super(Invoice, cls).get_commission_insurer_invoice_types() + [
            'all_insurer_invoices']

    def _get_move_line(self, date, amount):
        insurer_journal = None
        line = super(Invoice, self)._get_move_line(date, amount)
        configuration = Pool().get('account.configuration').get_singleton()
        if configuration is not None:
            insurer_journal = configuration.insurer_payment_journal
        if (getattr(self, 'business_kind', None) in
                self.get_commission_insurer_invoice_types() and
                self.type == 'in' and self.total_amount > 0
                and insurer_journal is not None):
            line.payment_date = line.maturity_date or utils.today()
        return line
