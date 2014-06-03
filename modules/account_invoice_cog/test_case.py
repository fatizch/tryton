from trytond.pool import PoolMeta

MODULE_NAME = 'account_invoice_cog'

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def new_fiscal_year(cls, start_date):
        translater = cls.get_translater(MODULE_NAME)
        translater_account = cls.get_translater('account_cog')
        result = super(TestCaseModel, cls).new_fiscal_year(start_date)
        result.in_credit_note_sequence = {
            'company': cls.get_company(),
            'name': '%s - %s %s' % (translater('In Credit Note Sequence'),
                translater_account('Fiscal Year'), start_date.year),
            'code': 'account.invoice',
            }
        result.in_invoice_sequence = {
            'company': cls.get_company(),
            'name': '%s - %s %s' % (translater('In Invoice Sequence'),
                translater_account('Fiscal Year'), start_date.year),
            'code': 'account.invoice',
            }
        result.out_credit_note_sequence = {
            'company': cls.get_company(),
            'name': '%s - %s %s' % (translater('Out Credit Note Sequence'),
                translater_account('Fiscal Year'), start_date.year),
            'code': 'account.invoice',
            }
        result.out_invoice_sequence = {
            'company': cls.get_company(),
            'name': '%s - %s %s' % (translater('Out Invoice Sequence'),
                translater_account('Fiscal Year'), start_date.year),
            'code': 'account.invoice',
            }
        return result
