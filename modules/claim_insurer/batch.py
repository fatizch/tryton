# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from trytond.pool import Pool, PoolMeta
from trytond.transaction import Transaction

from trytond.modules.commission_insurer import batch as commission_batch


__all__ = [
    'CreateEmptyInvoicePrincipalBatch',
    'LinkInvoicePrincipalBatch',
    'FinalizeInvoicePrincipalBatch',
    ]


class BaseInvoicePrincipalBatch(commission_batch.BaseInvoicePrincipalBatch):

    @classmethod
    def possible_notice_kind(cls):
        return super(BaseInvoicePrincipalBatch, cls).possible_notice_kind(
            ) + ('benefits',)

    @classmethod
    def get_principal_line_description(cls, notice_kind):
        if notice_kind == 'benefits':
            return Pool().get('account.invoice'
                ).raise_user_error('batch_claims_paid',
                    raise_exception=False)
        return super(BaseInvoicePrincipalBatch, cls
            ).get_principal_line_description(notice_kind)

    @classmethod
    def get_insurers(cls, notice_kind):
        # Because this method is called from batch, it is possible that
        # the company is not set. So the MultiValue field could not be
        # resolved properly.
        with Transaction().set_context(company=1):
            if notice_kind == 'benefits':
                Insurer = Pool().get('insurer')
                insurers = Insurer.search(['benefits', '!=', None])
                return list({
                        x[0] for x in Insurer.get_insurers_waiting_accounts(
                            insurers, 'benefits')})
        return super(BaseInvoicePrincipalBatch, cls).get_insurers(notice_kind)


# Batches below are redifined just to implement the overrided
# BaseInvoicePrincipalBatch class above.
# By doing this, When retrieving batch from the Pool,
# BaseInvoicePrincipalBatch override will be applied even if it is not
# registered into the Pool


class CreateEmptyInvoicePrincipalBatch(BaseInvoicePrincipalBatch):
    __metaclass__ = PoolMeta
    __name__ = 'commission.invoice_principal.create_empty'


class LinkInvoicePrincipalBatch(BaseInvoicePrincipalBatch):
    __metaclass__ = PoolMeta
    __name__ = 'commission.invoice_principal.link'


class FinalizeInvoicePrincipalBatch(BaseInvoicePrincipalBatch):
    __metaclass__ = PoolMeta
    __name__ = 'commission.invoice_principal.finalize'
