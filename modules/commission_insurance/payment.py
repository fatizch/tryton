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

    def get_payment_journal(self, line):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if not isinstance(line.origin, Invoice):
            return super(Configuration, self).get_payment_journal(line)
        if not line.origin.is_commission_invoice:
            return super(Configuration, self).get_payment_journal(line)
        journal = self.broker_bank_transfer_journal \
            if line.origin.party.bank_transfert_payment \
            else self.broker_check_journal
        return journal or super(Configuration, self).get_payment_journal(line)
