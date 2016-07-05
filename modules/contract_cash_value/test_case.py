# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache

MODULE_NAME = 'contract_cash_value'

__metaclass__ = PoolMeta

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    'Test Case Model'

    __name__ = 'ir.test_case'

    _get_journal_cache = Cache('get_journal')

    @classmethod
    def create_journal(cls, **kwargs):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Journal = pool.get('account.journal')
        if 'sequence' not in kwargs:
            kwargs['sequence'] = Sequence.search([
                    ('code', '=', 'account.journal')])[0].id
        return Journal(**kwargs)

    @classmethod
    def journal_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        journals = []
        journals.append(cls.create_journal(
                name=translater('Cash Value Journal'),
                type='general',
                code='cash_value'))
        return journals

    @classmethod
    def get_journal(cls, name):
        result = cls._get_journal_cache.get(name)
        if result:
            return result
        result = Pool().get('account.journal').search([
                ('name', '=', name)], limit=1)[0]
        cls._get_journal_cache.set(name, result)
        return result

    @classmethod
    def configure_accounting_test_case(cls):
        super(TestCaseModel, cls).configure_accounting_test_case()
        translater = cls.get_translater(MODULE_NAME)
        account_config = Pool().get('account.configuration').search([])[0]
        if not account_config.cash_value_journal:
            account_config.cash_value_journal = cls.get_journal(
                translater('Cash Value Journal'))
            account_config.save()
