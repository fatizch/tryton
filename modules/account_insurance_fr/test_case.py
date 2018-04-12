# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool


__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'
    __metaclass__ = PoolMeta

    @classmethod
    def update_check_journal(cls):
        pool = Pool()
        StatementJournal = pool.get('account.journal')
        Account = pool.get('account.account')

        translater = cls.get_translater('account_statement_cog')
        statement_journals = StatementJournal.search([
                ('name', '=', translater('Check'))])
        if not statement_journals:
            return
        debit_credit_accounts = Account.search([
                ('code', '=', '512')], limit=1)
        if not debit_credit_accounts:
            return
        for statement_journal in statement_journals:
            statement_journal.credit_account = debit_credit_accounts[0]
            statement_journal.debit_account = debit_credit_accounts[0]
            statement_journal.save()

    @classmethod
    def update_SEPA_journal(cls):
        pool = Pool()
        PaymentJournal = pool.get('account.payment.journal')
        Account = pool.get('account.account')
        Journal = pool.get('account.journal')
        Sequence = pool.get('ir.sequence')

        translater = cls.get_translater('account_payment_sepa_cog')
        if translater:
            payment_journals = PaymentJournal.search([
                    ('name', '=', translater('SEPA Direct Debit'))], limit=1)
            accounts = Account.search([('code', '=', '512')], limit=1)
            if payment_journals and accounts:
                sequence = Sequence.search([
                        ('code', '=', 'account.journal')])[0]
                journal = Journal(
                    name=translater('SEPA Direct Debit'),
                    code='SEPA',
                    active=True,
                    type='general',
                    sequence=sequence,
                    )
                journal.save()
                for payment_journal in payment_journals:
                    if hasattr(payment_journal, 'clearing_account'):
                        payment_journal.clearing_account = accounts[0]
                        payment_journal.clearing_journal = journal
                        payment_journal.save()

    @classmethod
    def account_test_case(cls):
        super(TestCaseModel, cls).account_test_case()
        configuration = cls.get_instance()
        if (configuration.account_template is not None and
                configuration.account_template.code == 'PCS'):
            pool = Pool()
            Account = pool.get('account.account')
            Account_Configuration = pool.get('account.configuration')
            account_configuration, = Account_Configuration.search([], limit=1)
            if account_configuration:
                account_configuration.default_account_receivable, = \
                    Account.search([('code', '=', '4117')], limit=1)
                account_configuration.default_account_payable, = \
                    Account.search([('code', '=', '4011')], limit=1)
                account_configuration.save()

    @classmethod
    def configure_accounting_test_case(cls):
        super(TestCaseModel, cls).configure_accounting_test_case()
        cls.update_check_journal()
        cls.update_SEPA_journal()
