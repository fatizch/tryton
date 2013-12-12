from trytond.pool import PoolMeta, Pool
from trytond.cache import Cache

MODULE_NAME = 'cash_value_contract'

__metaclass__ = PoolMeta

__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    'Test Case Model'

    __name__ = 'ir.test_case'

    _get_journal_cache = Cache('get_journal')

    @classmethod
    def _get_test_case_dependencies(cls):
        result = super(TestCaseModel, cls)._get_test_case_dependencies()
        result['configure_accounting_test_case']['dependencies'].add(
            'journal_test_case')
        result['journal_test_case'] = {
            'name': 'Journal Test Case',
            'dependencies': set(['main_company_test_case']),
        }
        return result

    @classmethod
    def create_journal(cls, name, journal_type, code):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        Journal = pool.get('account.journal')
        journal = Journal()
        journal.name = name
        journal.type = journal_type
        journal.code = code
        journal.sequence = Sequence.search([
                ('code', '=', 'account.journal')])[0].id
        return journal

    @classmethod
    def journal_test_case(cls):
        translater = cls.get_translater(MODULE_NAME)
        journals = []
        journals.append(cls.create_journal(translater(
                    'Cash Value Journal'), 'general', 'cash_value'))
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
        result = super(TestCaseModel, cls).configure_accounting_test_case()
        translater = cls.get_translater(MODULE_NAME)
        account_config = Pool().get('account.configuration').search([])[0]
        if not account_config.cash_value_journal:
            account_config.cash_value_journal = cls.get_journal(
                translater('Cash Value Journal'))
            account_config.save()
        return result
