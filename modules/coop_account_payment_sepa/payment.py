import datetime
import os

import genshi
import genshi.template

from trytond.pool import Pool, PoolMeta
from trytond.model import fields
from trytond.pyson import Eval

__metaclass__ = PoolMeta
__all__ = ['Journal', 'Group', 'Payment']


loader = genshi.template.TemplateLoader(
    os.path.join(os.path.dirname(__file__), 'template'),
    auto_reload=True)


def remove_comment(stream):
    for kind, data, pos in stream:
        if kind is genshi.core.COMMENT:
            continue
        yield kind, data, pos


class Journal:
    __name__ = 'account.payment.journal'
    sepa_bank_account_number = fields.Many2One('party.bank_account_number',
        'Bank Account', states={
            'required': Eval('process_method') == 'sepa',
            'invisible': Eval('process_method') != 'sepa',
            },
        domain=[('kind', '=', 'IBAN')],  # TODO filter on party company
        depends=['process_method'])

    @classmethod
    def __setup__(cls):
        super(Journal, cls).__setup__()
        sepa_method = ('sepa', 'Sepa')
        if sepa_method not in cls.process_method.selection:
            cls.process_method.selection.append(sepa_method)


class Group:
    __name__ = 'account.payment.group'
    sepa_msg = fields.Text('Sepa Message', readonly=True)

    def process_sepa(self):
        if self.kind == 'payable':
            raise NotImplementedError
        elif self.kind == 'receivable':
            tmpl = loader.load('pain.008.001.04.xml')
        self.sepa_msg = tmpl.generate(group=self,
            datetime=datetime).filter(remove_comment).render()
        for payment in self.payments:
            payment.state = 'succeeded'
            payment.save()


class Payment:
    __name__ = 'account.payment'

    @property
    def sepa_mandate(self):
        # XXX
        class Mandate(object):
            __name__ = 'Mandate object'
            reference = 'ABCD123'
            signature_date = datetime.date.today()
            electronic_signature = False
            first_date = None
            final_date = None
            frequency = 'MNTH'
        return Mandate()

    @property
    def sepa_end_to_end_id(self):
        pool = Pool()
        Contract = pool.get('contract.contract')

        if self.line and isinstance(self.line.move.origin, Contract):
            contract = self.line.move.origin
            return contract.contract_number

    @property
    def sepa_bank_account_number(self):
        pool = Pool()
        Contract = pool.get('contract.contract')

        if self.line and isinstance(self.line.move.origin, Contract):
            contract = self.line.move.origin
            billing_manager = contract.get_billing_manager(self.line.date)
            assert billing_manager, 'Missing Billing Manager'
            if billing_manager.payment_bank_account:
                for account_number in \
                        billing_manager.payment_bank_account.account_numbers:
                    if account_number.kind == 'IBAN':
                        return account_number
