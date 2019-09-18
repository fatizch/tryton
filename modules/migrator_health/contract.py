# coding: utf-8

from itertools import groupby
from sql import Table

from trytond import backend
from trytond.pool import Pool, PoolMeta

from trytond.modules.migrator import migrator, tools

DatabaseOperationalError = backend.get('DatabaseOperationalError')


__all__ = [
    'MigratorContractHealthOption',
    'MigratorContract',
    ]


class MigratorContractHealthOption(migrator.Migrator):
    """Migrator contract health option"""

    __name__ = 'migrator.contract.health.option'

    @classmethod
    def __setup__(cls):
        super(MigratorContractHealthOption, cls).__setup__()
        cls.table = Table('option')
        cls.func_key = 'contract_number'
        cls.columns = {k: k for k in ('contract_number',
            'covered_element', 'noemie_status', 'noemie_return_code',
            'noemie_return_message', 'noemie_start_date', 'noemie_end_date',
            'option', 'start_date', 'end_date',
            'covered_element_extra_data', 'extra_data')}
        cls.error_messages.update({
                'no_option': "no option for contract",
                })

    @classmethod
    def init_cache(cls, rows, **kwargs):
        cls.cache_obj['coverage'] = tools.cache_from_search(
            'offered.option.description', 'code')
        cls.cache_obj['contract'] = tools.cache_from_search('contract',
            'contract_number', ('contract_number', 'in', [r['contract_number']
                for r in rows]))
        cls.cache_obj['party'] = tools.cache_from_search('party.party',
            'code', ('code', 'in', [r['covered_element'] for r in rows]))

    @classmethod
    def populate(cls, row):
        row = super(MigratorContractHealthOption, cls).populate(row)
        cls.resolve_key(row, 'contract_number', 'contract', 'contract')
        cls.resolve_key(row, 'option', 'coverage', 'coverage')
        cls.resolve_key(row, 'covered_element', 'party', 'party')
        return row

    @classmethod
    def group_func(cls, x):
        return (x['contract_number'], x['covered_element'])

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        pool = Pool()

        Contract = pool.get('contract')
        to_create = {}
        contracts_in_error = []
        for keys, _rows in groupby(sorted(rows, key=cls.group_func),
                key=cls.group_func):
            rowslist = list(_rows)
            try:
                rows = [cls.populate(r) for r in rowslist]
            except migrator.MigrateError as e:
                cls.logger.error(e)
                contracts_in_error.append(keys)
                continue
            contract = rows[0]['contract']
            the_covered_element = cls.create_covered_element(rows)
            the_covered_element[0].options = cls.create_options_covered_element(
                rows, the_covered_element[0])
            to_create[rows[0]['contract_number']] = contract
            Contract.save(list(to_create.values()))
        return to_create

    @classmethod
    def create_covered_element(cls, rows):
        pool = Pool()
        Version = pool.get('contract.covered_element.version')
        CoveredElement = pool.get('contract.covered_element')
        covered_element_version = Version(**Version.get_default_version())
        covered_element_version = {'extra_data': {}}
        if rows[0]['covered_element_extra_data']:
            covered_element_version['extra_data'] = eval(
                rows[0]['covered_element_extra_data'])
            covered_element = CoveredElement.create([{
                'contract': rows[0]['contract'],
                'item_desc': rows[0]['coverage'].item_desc,
                'noemie_return_code': rows[0]['noemie_return_code'],
                'noemie_update_date': rows[0]['noemie_start_date'],
                'noemie_start_date': rows[0]['noemie_start_date'],
                'noemie_end_date': rows[0]['noemie_end_date'],
                'party': rows[0]['party'],
                'versions': [('create', [covered_element_version])]
                }])
        return covered_element

    @classmethod
    def create_options_covered_element(cls, rows, the_covered_element):
        pool = Pool()
        Option = pool.get('contract.option')
        options = []
        for row in rows:
            option_version = {'extra_data': {}}
            if row['extra_data']:
                option_version['extra_data'] = eval(row['extra_data'])
            option = Option.create([{
                'covered_element': the_covered_element,
                'status': 'active',
                'coverage': row['coverage'],
                'versions': [('create', [option_version])]
            }])
            options.extend(option)
        return options


class MigratorContract(metaclass=PoolMeta):
    __name__ = 'migrator.contract'

    @classmethod
    def extra_migrator_names(cls):
        migrators = super(MigratorContract, cls).extra_migrator_names()
        return migrators + ['migrator.contract.health.option']
