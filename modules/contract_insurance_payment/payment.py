# -*- coding:utf-8 -*-
from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Payment',
    'Journal',
    ]


class Journal:
    __name__ = 'account.payment.journal'

    failure_billing_mode = fields.Many2One('offered.billing_mode',
        'Failure Billing Mode',
        domain=[('direct_debit', '=', False)],
        states={
            'required': Eval('process_method').in_(['sepa']),
            },
        depends=['process_method'])


class Payment:
    __name__ = 'account.payment'

    @classmethod
    def fail_manual(cls, payments):
        super(Payment, cls).fail_manual(payments)
        pool = Pool()
        Invoice = pool.get('account.invoice')
        ContractBillingInformation = pool.get('contract.billing_information')
        Date = pool.get('ir.date')

        for payment in payments:
            if not isinstance(payment.line.move.origin, Invoice):
                break
            contract = payment.line.move.origin.contract
            if not contract:
                break
            failure_billing_mode = payment.journal.failure_billing_mode
            if not failure_billing_mode:
                raise Exception('no failure_billing_mode on journal %s'
                    % (payment.journal.rec_name))

            ContractBillingInformation.copy([
                contract.billing_information], {
                'date': Date.today(),
                'billing_mode': failure_billing_mode,
                'payment_term':
                    contract.product.billing_modes[0].allowed_payment_terms[0],
                })

    @classmethod
    def fail_retry(cls, payments):
        super(Payment, cls).fail_retry()
        pool = Pool()
        Invoice = pool.get('account.invoice')
        MoveLine = pool.get('account.move.line')

        payment_line_to_modify = []
        for payment in payments:
            if not isinstance(payment.line.move.origin, Invoice):
                break
            contract_invoice = payment.line.move.origin.contract_invoice
            invoice = payment.line.move.origin

            if not contract_invoice:
                break
            with Transaction().set_context(
                    contract_revision_date=contract_invoice.start):
                res = invoice.udpate_move_line_from_billing_information(
                    payment.line,
                    contract_invoice.contract.billing_information)
                for field_name, field_value in res.iteritems():
                    setattr(payment.line, field_name, field_value)
                payment_line_to_modify += [[payment.line], {
                            'payment_date': payment.line.payment_date
                        }]

        if payment_line_to_modify:
            MoveLine.write(*payment_line_to_modify)
