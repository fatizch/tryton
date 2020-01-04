# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from sql import Table
from itertools import groupby

from trytond.modules.migrator import tools
from trytond.modules.migrator import migrator
from trytond.pool import PoolMeta, Pool


__all__ = [
    'MigratorPartyEmployment',
    'MigratorPartyPublicEmployment',
    'MigratorPartyPublicEmploymentFr',
    ]

mapping_fr_subdivision = {
    '971': 'GP',
    '972': 'MQ',
    '973': 'GF',
    '974': 'RE',
    '976': 'YT',
    }


class MigratorPartyEmployment(migrator.Migrator):
    """Migrator Party Employment"""
    __name__ = 'migrator.party.employment'

    @classmethod
    def __setup__(cls):
        super(MigratorPartyEmployment, cls).__setup__()
        cls.table = Table('employment')
        cls.model = 'party.employment'
        cls.func_key = 'employee'
        cls.columns = {k: k for k in ('employer', 'employment_identifier',
                'work_section', 'employment_kind')}
        cls.columns['start_date'] = 'employment_start_date'
        cls.columns['end_date'] = 'employment_end_date'
        cls.columns['employee'] = 'party'
        cls.columns['work_time_type'] = 'work_time_type'
        cls.columns['gross_salary'] = 'gross_salary'
        cls.columns['date'] = 'effective_date'
        cls.error_messages.update({
            'date_error': 'date is mandatory field on employment version',
        })

    @classmethod
    def init_cache(cls, rows, **kwargs):
        cls.cache_obj['work_section'] = tools.cache_from_search(
            'party.work_section', 'code', ('code', 'in', [r['work_section']
                for r in rows]))
        cls.cache_obj['employment_kind'] = tools.cache_from_search(
            'party.employment_kind', 'code')
        cls.cache_obj['employee'] = tools.cache_from_search('party.party',
            'code', ('code', 'in', [r['employee'] for r in rows]))
        cls.cache_obj['employer'] = tools.cache_from_search('party.identifier',
            'code', ('code', 'in', [r['employer'] for r in rows]))
        cls.cache_obj['work_time_type'] = tools.cache_from_search(
            'party.employment_work_time_type', 'code', ('code', 'in',
            [r['work_time_type'] for r in rows]))

    @classmethod
    def populate(cls, row):
        row['employee'] = cls.cache_obj['employee'][row['employee']]
        row['employer'] = cls.cache_obj['employer'][row['employer']].party if\
            row['employer'] else None
        row['work_section'] = cls.cache_obj['work_section'][row[
            'work_section']] if row['work_section'] else None
        # TO DO JUST TEMPORARY
        row['employment_kind'] = cls.cache_obj['employment_kind'][row[
            'employment_kind']] if row['employment_kind'] else None
        return row

    @classmethod
    def sanitize(cls, row):
        row['entry_date'] = row['start_date']
        return row

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        pool = Pool()
        to_upsert = {}
        sorted(rows, key=lambda x: (x['employee'], x['employer']))
        for employment, _rows in groupby(rows, key=lambda x: (x['employee'],
                x['employer'])):
            version_rows = list(_rows)
            employment_row = cls.populate(version_rows[0])
            to_create = []
            for row in version_rows:
                if row['date']:
                    version_row = cls.populate_version_row(row)
                    if version_row:
                        to_create.append(version_row)
                else:
                    cls.raise_error('date_error')
            if to_create:
                employment_row['versions'] = [('create', to_create)]
            to_upsert[employment] = cls.remove_version_information(
                employment_row)
        if to_upsert:
            cls.upsert_records(list(to_upsert.values()), **kwargs)
            for migrator_name in cls.extra_migrator_names():
                pool.get(migrator_name).migrate(list(to_upsert.keys()),
                    **kwargs)
        return to_upsert

    @classmethod
    def remove_version_information(cls, row):
        if 'gross_salary' in row:
            row.pop('gross_salary')
        if 'work_time_type' in row:
            row.pop('work_time_type')
        if 'date' in row:
            row.pop('date')
        return row

    @classmethod
    def populate_version_row(cls, row):
        row['work_time_type'] = cls.cache_obj['work_time_type'][row[
            'work_time_type']] if row['work_time_type'] else None
        return {'work_time_type': row['work_time_type'],
            'gross_salary': row['gross_salary'], 'date': row['date']}


class MigratorPartyPublicEmployment(metaclass=PoolMeta):
    __name__ = 'migrator.party.employment'

    @classmethod
    def __setup__(cls):
        super(MigratorPartyPublicEmployment, cls).__setup__()
        cls.columns['administrative_situation'] = 'administrative_situation'
        cls.columns['date'] = 'effective_date'
        cls.columns['public_service_work_category'] = 'statutory_category'
        cls.columns['increased_index'] = 'increased_index'
        cls.columns['work_subdivision'] = 'work_subdivision'
        cls.columns['administrative_situation_sub_status'] = \
            'administrative_situation_complement'

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorPartyPublicEmployment, cls).init_cache(rows)
        cls.cache_obj['administrative_situation_sub_status'] = \
            tools.cache_from_search('party.administrative_situation_sub_status',
            'code', ('code', 'in',
                [r['administrative_situation_sub_status'] for r in rows]))
        cls.cache_obj['public_service_work_category'] = \
            tools.cache_from_search('party.public_service_work_category',
            'code', ('code', 'in',
                list(set([r['public_service_work_category'] for r in rows]))))
        cls.cache_obj['work_subdivision'] = tools.cache_from_search(
            'country.subdivision', 'code', ('code', 'in',
                list(set([r['work_subdivision'] for r in rows]))))

    @classmethod
    def remove_version_information(cls, row):
        row = super(MigratorPartyPublicEmployment,
            cls).remove_version_information(row)
        if 'administrative_situation' in row:
            row.pop('administrative_situation')
        if 'administrative_situation_complement' in row:
            row.pop('administrative_situation_complement')
        if 'increased_index' in row:
            row.pop('increased_index')
        if 'work_subdivision' in row:
            row.pop('work_subdivision')
        return row

    @classmethod
    def populate_version_row(cls, row):
        version_row_dict = super(MigratorPartyPublicEmployment,
            cls).populate_version_row(row)
        version_row_dict.update({
            'administrative_situation': row['administrative_situation'],
            'increased_index': row['increased_index'],
            'work_subdivision': cls.cache_obj['work_subdivision'][
                    row['work_subdivision']]
            if row['work_subdivision'] else None,
            'administrative_situation_sub_status':
                cls.cache_obj['administrative_situation_sub_status'][
                    row['administrative_situation_sub_status']]
                if row['administrative_situation_sub_status'] else None,
            'public_service_work_category':
                cls.cache_obj['public_service_work_category'][
                    row['public_service_work_category']]
                if row['public_service_work_category'] else None,
            })
        return version_row_dict

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorPartyPublicEmployment, cls).sanitize(row)
        if row['work_subdivision']:
            suffix = row['work_subdivision']
            if row['work_subdivision'] in mapping_fr_subdivision:
                suffix = mapping_fr_subdivision[row['work_subdivision']]
            row['work_subdivision'] = 'FR-' + suffix
        return row


class MigratorPartyPublicEmploymentFr(metaclass=PoolMeta):
    __name__ = 'migrator.party.employment'

    @classmethod
    def __setup__(cls):
        super(MigratorPartyPublicEmploymentFr, cls).__setup__()
        cls.columns['csrh'] = 'csrh'
        cls.columns['payroll_subdivision'] = 'payroll_management_subdivision'
        cls.columns['salary_deduction_service'] = 'salary_deduction_service'
        cls.columns['payroll_assignment_number'] = 'assignment_service'
        cls.columns['payroll_care_number'] = 'care_number'

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorPartyPublicEmploymentFr, cls).init_cache(rows)
        cls.cache_obj['csrh'] = tools.cache_from_search('csrh', 'code',
            ('code', 'in', [r['csrh'] for r in rows]))
        cls.cache_obj['payroll_service'] = tools.cache_from_search(
            'party.payroll_service', 'code',
            ('code', 'in', [r['csrh'] for r in rows]))
        cls.cache_obj['payroll_subdivision'] = tools.cache_from_search(
            'country.subdivision', 'code',
            ('code', 'in', [r['payroll_subdivision'] for r in rows]))
        cls.cache_obj['salary_deduction_service'] = tools.cache_from_search(
            'party.salary_deduction_service', 'code',
            ('code', 'in', [r['salary_deduction_service'] for r in rows]))

    @classmethod
    def populate(cls, row):
        row = super(MigratorPartyPublicEmploymentFr, cls).populate(row)
        row['csrh'] = cls.cache_obj['csrh'][row['csrh']] if row['csrh'] else \
            None
        row['payroll_subdivision'] = cls.cache_obj['payroll_subdivision'][row[
            'payroll_subdivision']] if row['payroll_subdivision'] else None
        row['salary_deduction_service'] = cls.cache_obj[
            'salary_deduction_service'][row['salary_deduction_service']] if \
            row['salary_deduction_service'] else None
        return row

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorPartyPublicEmploymentFr, cls).sanitize(row)
        if row['payroll_subdivision']:
            suffix = row['payroll_subdivision']
            if row['payroll_subdivision'] in mapping_fr_subdivision:
                suffix = mapping_fr_subdivision[row['payroll_subdivision']]
            row['payroll_subdivision'] = 'FR-' + suffix
        return row
