from trytond.pool import Pool, PoolMeta
from .agency_loader import AgenciesLoader

__metaclass__ = PoolMeta
__all__ = [
    'TestCaseModel',
    ]


class TestCaseModel:
    __name__ = 'ir.test_case'

    @classmethod
    def bank_test_case(cls):
        super(TestCaseModel, cls).bank_test_case()
        pool = Pool()
        Bank = pool.get('bank')
        Agency = pool.get('bank.agency')
        banks = {x.bic: x.id for x in Bank.search([])}
        agencies = {(a.bank.bic, a.bank_code, a.branch_code): a
            for a in Agency.search([])}
        bank_file = cls.read_csv_file('branch.csv', 'bank_fr',
            reader='dict')
        to_create = []
        for agency in bank_file:
            bic = '%sXXX' % agency['bic'] if len(agency['bic']) == 8 \
                else agency['bic']
            bank_code = str(agency['bank_code']).zfill(5)
            branch_code = str(agency['branch_code']).zfill(5)
            if (bic, bank_code, branch_code) in agencies:
                continue
            bank = banks.get(bic, None)
            if not bank:
                continue
            to_create.append({
                    'bank': bank,
                    'bank_code': bank_code,
                    'branch_code': branch_code,
                    'name': agency['name'],
                    })
        if to_create:
            Agency.create(to_create)

    @classmethod
    def agencies_test_case(cls):
        logger = cls.get_logger()
        cls.load_resources('bank_fr')
        file_path = cls._loaded_resources['bank_fr']['files']['agencies.csv']
        AgenciesLoader.execute(file_path, logger)
