# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import PYSONEncoder, PYSONDecoder
from trytond.transaction import Transaction

__all__ = [
    'Commission',
    ]


class Commission:
    __metaclass__ = PoolMeta
    __name__ = 'commission'

    @classmethod
    def __setup__(cls):
        super(Commission, cls).__setup__()
        cls._error_messages.update({
                'missing_broker_analytic_account': 'Broker analytic '
                'account to use is missing. Do you want to continue?'
                })

    @classmethod
    def invoice(cls, commissions):
        super(Commission, cls).invoice(commissions)
        invoices = list(set([c.invoice_line.invoice for c in commissions]))
        pool = Pool()
        AccountConfiguration = pool.get('account.configuration')
        account_configuration = AccountConfiguration(1)

        AnalyticAccount = pool.get('analytic_account.account')
        InvoiceLine = pool.get('account.invoice.line')

        context = Transaction().context.copy()
        context['context'] = context
        analytic_accounts_domain = PYSONDecoder(context).decode(
            PYSONEncoder().encode(InvoiceLine.analytic_accounts.domain))

        root_accounts = AnalyticAccount.search(
            analytic_accounts_domain + [
                ('parent', '=', None),
                ])
        accounts = []
        broker_analytic_account_to_use = \
            account_configuration.broker_analytic_account_to_use
        if (broker_analytic_account_to_use
                and broker_analytic_account_to_use.root in root_accounts):
            accounts.append({
                'required': broker_analytic_account_to_use.root.mandatory,
                'root': broker_analytic_account_to_use.root,
                'account': broker_analytic_account_to_use
                })
        else:
            cls.raise_user_warning('missing_broker_analytic_account',
                'missing_broker_analytic_account')
            for account in root_accounts:
                accounts.append({
                    'required': account.mandatory,
                    'root': account.id,
                    })
        to_write = []
        for invoice in invoices:
            for line in invoice.lines:
                line.analytic_accounts = accounts
                to_write.append(line)
        if to_write:
            InvoiceLine.save(to_write)
        return invoices
