# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool

from trytond.modules.coog_core import fields


__all__ = [
    'Configuration',
    ]


class Configuration:
    __metaclass__ = PoolMeta
    __name__ = 'account.configuration'

    insurer_payment_journal = fields.Many2One('account.payment.journal',
        'Insurer Payment Journal', ondelete='RESTRICT',
        help='Configure the default payment journal for insurer ',
        domain=[('process_method', '!=', 'manual')])
    insurer_manual_payment_journal = fields.Many2One('account.payment.journal',
        'Insurer Check Journal', ondelete='RESTRICT', help='Configure '
        'the check payment journal for insurer ')
    insurer_invoice_payment_term = fields.Many2One(
        'account.invoice.payment_term', 'Insurer Invoice Payment Term',
        ondelete='RESTRICT', help='Configure the insurer commission invoice '
        'payment term')

    def get_payment_journal(self, line):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        if ((not isinstance(getattr(line, 'origin', None), Invoice))
                or (line.origin.id < 0)):
            return super(Configuration, self).get_payment_journal(line)
        if not (line.origin.business_kind == 'insurer_invoice' and
                line.origin.type == 'in'):
            return super(Configuration, self).get_payment_journal(line)
        journal = self.insurer_payment_journal \
            if line.origin.party.automatic_wire_transfer \
            else self.insurer_manual_payment_journal
        return journal or super(Configuration, self).get_payment_journal(line)
