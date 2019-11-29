# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields, utils


__all__ = [
    'Configuration',
    ]


class Configuration(metaclass=PoolMeta):
    __name__ = 'account.configuration'

    paybox_direct_debit_journal = fields.Many2One('account.payment.journal',
        'Paybox Direct Debit Journal', ondelete='RESTRICT',
        help='Default Paybox payment journal')

    def get_payment_journal(self, line):
        PaymentJournal = Pool().get('account.payment.journal')
        forced_journal = Transaction().context.get('forced_payment_journal',
            None)
        if forced_journal:
            return PaymentJournal(forced_journal)
        contract_revision_date = getattr(line, 'payment_date', None) \
            or line.maturity_date or utils.today()
        AccountConfiguration = Pool().get('account.configuration')
        account_configuration = AccountConfiguration(1)
        journal = None
        with Transaction().set_context(
                contract_revision_date=contract_revision_date):
            if (line.contract and line.contract.billing_information and
                    line.contract.billing_information.process_method ==
                    'paybox'):
                journal = (line.contract.product.paybox_payment_journal or
                    account_configuration.paybox_direct_debit_journal)
        return journal or super().get_payment_journal(line)
