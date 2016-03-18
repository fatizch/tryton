from trytond.pool import PoolMeta, Pool

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Configuration',
    ]


class Configuration:
    __name__ = 'account.configuration'

    broker_bank_transfer_journal = fields.Many2One('account.payment.journal',
        'Broker Bank Transfer Journal',
        domain=[('process_method', '!=', 'manual')])
    broker_check_journal = fields.Many2One('account.payment.journal',
        'Broker Check Journal')
    commission_invoice_payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Commission Invoice Payment Term',
        ondelete='SET NULL')

    def get_payment_journal(self, line):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if not isinstance(getattr(line, 'origin', None), Invoice):
            return super(Configuration, self).get_payment_journal(line)
        if not (line.origin.business_kind == 'broker_invoice' and
                line.origin.type == 'in_invoice'):
            return super(Configuration, self).get_payment_journal(line)
        journal = self.broker_bank_transfer_journal \
            if line.origin.party.automatic_wire_transfer \
            else self.broker_check_journal
        return journal or super(Configuration, self).get_payment_journal(line)
