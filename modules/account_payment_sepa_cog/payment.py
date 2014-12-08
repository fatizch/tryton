import os
from itertools import groupby
from collections import namedtuple

import genshi
import genshi.template

from trytond.pool import PoolMeta, Pool
from trytond.model import fields
from trytond.modules.cog_utils import export

__metaclass__ = PoolMeta
__all__ = [
    'Mandate',
    'Group',
    'Payment',
    ]


loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Mandate(export.ExportImportMixin):
    __name__ = 'account.payment.sepa.mandate'

    def get_rec_name(self, name):
        if self.identification is None or self.party is None:
            return super(Mandate, self).get_rec_name(name)
        return '%s - %s' % (self.identification, self.party.get_rec_name(None))

    @classmethod
    def _export_skips(cls):
        return (super(Mandate, cls)._export_skips() |
            set(['payments', 'party']))

    @classmethod
    def _export_light(cls):
        return (super(Mandate, cls)._export_light() |
            set(['company', 'account_number']))


class Group:
    __name__ = 'account.payment.group'

    def sepa_merge_payment_key(self, payment):
        return (('party', payment.party),
            ('sepa_mandate', payment.sepa_mandate),
            ('sepa_bank_account_number', payment.sepa_bank_account_number),
            ('sepa_merged_id', payment.sepa_merged_id),
            ('currency', payment.currency),
            )

    def process_sepa(self):
        pool = Pool()
        Payment = pool.get('account.payment')
        Sequence = pool.get('ir.sequence')
        if self.kind == 'receivable':
            keyfunc = self.sepa_merge_payment_key
            payments = sorted(self.payments, key=keyfunc)
            for key, merged_payments in groupby(payments, key=keyfunc):
                Payment.write(list(merged_payments), {
                        'sepa_merged_id':
                        Sequence.get('account.payment.merged'),
                        })
        super(Group, self).process_sepa()

    @property
    def sepa_payments(self):
        Payment = namedtuple('Payment', [
                'sepa_instruction_id',
                'sepa_end_to_end_id',
                'currency',
                'amount',
                'sepa_mandate',
                'sepa_bank_account_number',
                'party',
                'sepa_remittance_information',
                ])
        keyfunc = self.sepa_merge_payment_key
        for key, grouped_payments in super(Group, self).sepa_payments:
            if self.kind == 'receivable':
                merged_payments = []
                grouped_payments = sorted(grouped_payments, key=keyfunc)
                for mkey, payments in groupby(grouped_payments, key=keyfunc):
                    mkey = dict(mkey)
                    amount = sum(p.amount for p in payments)
                    payment = Payment(
                        sepa_instruction_id=mkey['sepa_merged_id'],
                        sepa_end_to_end_id=mkey['sepa_merged_id'],
                        currency=mkey['currency'],
                        amount=amount,
                        sepa_mandate=mkey['sepa_mandate'],
                        sepa_bank_account_number=mkey[
                            'sepa_bank_account_number'],
                        party=mkey['party'],
                        sepa_remittance_information='',  # TODO
                        )
                    merged_payments.append(payment)
                yield key, merged_payments
            else:
                yield key, grouped_payments


class Payment:
    __name__ = 'account.payment'

    sepa_merged_id = fields.Char('SEPA Merged ID')

    def get_sepa_end_to_end_id(self, name):
        value = super(Payment, self).get_sepa_end_to_end_id(name)
        return self.sepa_merged_id or value

    @classmethod
    def search_end_to_end_id(cls, name, domain):
        result = super(Payment, cls).search_end_to_end_id(name, domain)
        return [
            'OR',
            [
                ('sepa_merged_id', '=', None),
                result,
                ],
            [
                ('sepa_merged_id',) + tuple(domain[1:]),
                ]
            ]
