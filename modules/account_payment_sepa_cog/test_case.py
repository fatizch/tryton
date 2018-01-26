# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

MODULE_NAME = 'account_payment_sepa_cog'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def create_SEPA_journal(cls):
        pool = Pool()
        PaymentJournal = pool.get('account.payment.journal')
        BankAccountNumber = pool.get('bank.account.number')
        translater = cls.get_translater(MODULE_NAME)
        Configuration = cls.get_instance()

        company = cls.get_company()
        bank_account_numbers = BankAccountNumber.search([(
                    ('type', '=', 'iban'),
                    ('account.owners', '=', company.id)
                    )])
        if bank_account_numbers:
            payment_journal = PaymentJournal(
                name=translater('SEPA Direct Debit'),
                currency=Configuration.currency,
                company=company,
                process_method='sepa',
                sepa_batch_booking=False,
                sepa_charge_bearer='SLEV',
                sepa_receivable_flavor='pain.008.001.04',
                sepa_payable_flavor='pain.001.001.03',
                sepa_bank_account_number=bank_account_numbers[0],
                )
            payment_journal.save()

    @classmethod
    def journal_test_case(cls):
        super(TestCaseModel, cls).journal_test_case()
        cls.create_SEPA_journal()
