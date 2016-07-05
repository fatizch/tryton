# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool, PoolMeta

MODULE_NAME = 'account_statement_cog'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def create_check_journal(cls):
        pool = Pool()
        Configuration = cls.get_instance()
        Journal = pool.get('account.journal')
        StatementJournal = pool.get('account.statement.journal')
        Sequence = pool.get('ir.sequence')
        translater = cls.get_translater(MODULE_NAME)

        sequence = Sequence.search([
                ('code', '=', 'account.journal')])[0]

        journal = Journal(
            name=translater('Check'),
            code='CHK',
            active=True,
            type='statement',
            sequence=sequence,
            )
        journal.save()

        statement_sequence = Sequence(
            company=cls.get_company(),
            name='Statement Sequence',
            code='statement'
            )
        statement_sequence.save()

        statement_journal = StatementJournal(
            name=translater('Check'),
            currency=Configuration.currency,
            company=cls.get_company(),
            journal=journal,
            sequence=statement_sequence,
            )
        statement_journal.save()

    @classmethod
    def journal_test_case(cls):
        super(TestCaseModel, cls).journal_test_case()
        cls.create_check_journal()
