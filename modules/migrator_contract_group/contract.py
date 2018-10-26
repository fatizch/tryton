# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from collections import defaultdict
from itertools import groupby

from sql import Table, Column, Literal, Null

from trytond.modules.migrator import Migrator, tools
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'MigratorContractGroup',
    'MigratorContractSubsidiary',
    'MigratorSubsidiaryAffiliated',
    'MigratorContractGroupConfiguration',
    ]


class BaseMigratorContractGroup(Migrator):

    @classmethod
    def __setup__(cls):
        super(BaseMigratorContractGroup, cls).__setup__()
        cls.table = Table('contracts')
        cls.model = 'contract'
        cls.func_key = 'contract_number'
        cls.columns = {
            'contract_number': 'contract_number',
            'party': 'party',
            'start_date': 'start_date',
            'end_date': 'end_date',
            'end_reason': 'end_reason',
            'signature_date': 'signature_date',
            'status': 'status',
            'product': 'product',
            'coverage': 'coverage',
            'external_number': 'external_number',
            'code': 'code',
            'extra_data': 'extra_data',
            'sub_extra_data': 'sub_extra_data',
            'item_desc': 'item_desc',
            }

    @classmethod
    def init_update_cache(cls, rows):
        ids = set([row[cls.func_key] for row in rows])
        cls.cache_obj['update'] = tools.cache_from_search('contract',
            'contract_number', ('contract_number', 'in', ids))

    @classmethod
    def init_cache(cls, rows, **kwargs):
        pool = Pool()
        Product = pool.get('offered.product')
        cls.cache_obj['product'] = defaultdict(dict)
        for product in Product.search([]):
            cls.cache_obj['product'][product.code] = product
        cls.cache_obj['party'] = tools.cache_from_search(
            'party.party', 'code',
            ('code', 'in', [r['party'] for r in rows]))
        cls.cache_obj['item_desc'] = tools.cache_from_search(
            'offered.item.description', 'code',
            ('code', 'in', [r['item_desc'] for r in rows]))
        cls.cache_obj['end_reason'] = tools.cache_from_search(
            'covered_element.end_reason', 'code')
        cls.cache_obj['contract'] = tools.cache_from_search(
            'contract', 'contract_number',
            ('contract_number', 'in', [r['contract_number'] for r in rows]))
        cls.cache_obj['coverage'] = tools.cache_from_search(
            'offered.option.description', 'code',
            ('code', 'in', [r['coverage'] for r in rows]))
        cls.cache_obj['company'] = tools.cache_from_search(
            'company.company', 'id', ('id', '=', 1))
        super(BaseMigratorContractGroup, cls).init_cache(rows, **kwargs)

    @classmethod
    def get_process_step(cls, process_name=None, default_step=None):
        pool = Pool()
        if process_name is None:
            process_name = batch._config.get(cls.__name__, 'process_name')
        if default_step is None:
            default_step = batch._config.get(cls.__name__, 'default_step')
        Process = pool.get('process')
        ProcessStep = pool.get('process.step')
        ProcessStepRelation = pool.get('process-process.step')
        process, = Process.search([('technical_name', '=', process_name)])
        process_step, = ProcessStep.search([
                ('technical_name', '=', default_step)
                ])
        step, = ProcessStepRelation.search([
                ('process', '=', process.id),
                ('step', '=', process_step.id)
                ])
        return step

    @classmethod
    def sanitize(cls, row):
        row = super(BaseMigratorContractGroup, cls).sanitize(row)
        row['start_date'] = datetime.datetime.strptime(row['start_date'],
            '%Y-%m-%d').date()
        row['end_date'] = datetime.datetime.strptime(row['end_date'],
            '%Y-%m-%d').date() if row['end_date'] else None
        row['signature_date'] = datetime.datetime.strptime(
            row['signature_date'], '%Y-%m-%d').date() \
            if row['signature_date'] else None
        return row

    @classmethod
    def do_update(cls, contract_number):
        if 'update' in cls.cache_obj:
            return contract_number in cls.cache_obj['update']
        return False

    @classmethod
    def init_covered_from_row(cls, row):
        item_desc = cls.cache_obj['item_desc'][row['item_desc']]
        res = {
            'item_desc': item_desc.id,
            'name': row['external_number'] if row['external_number'] else None,
            'manual_start_date': row['start_date'],
            'end_reason': cls.cache_obj['end_reason'][
                row['end_reason']]
            if row['end_reason'] else None,
            }
        data = {'extra_data': {}}
        if row['sub_extra_data']:
            data['extra_data'] = eval(row['sub_extra_data'])
            data['start'] = row['start_date']
        res['versions'] = [('create', [data])]
        return res


class MigratorContractGroup(BaseMigratorContractGroup):
    'Migrate Contracts Groups'
    __name__ = 'migrator.contract.group'

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorContractGroup, cls).init_cache(rows, **kwargs)
        cls.cache_obj['process_step'] = cls.get_process_step()

    @classmethod
    def create_activation_history(cls, contract_lines):
        activation_history = {}
        start_date = min([d['start_date'] for d in contract_lines])
        end_date = [d['end_date'] for d in contract_lines
                if d['end_date']]
        all_with_end_date = all([d['end_date'] for d in contract_lines])
        activation_history['start_date'] = start_date
        activation_history['end_date'] = max(end_date) if all_with_end_date \
            else None
        return activation_history

    @classmethod
    def create_endorsement(cls, contract, activation_history):
        pool = Pool()
        Endorsement = pool.get('endorsement')
        Definition = pool.get('endorsement.definition')
        termination = Definition.get_definition_by_code('stop_contract')
        reactivate = Definition.get_definition_by_code('reactivate_contract')
        for history in contract.activation_history:
            if history.start_date == activation_history['start_date']:
                if activation_history['end_date'] != contract.end_date \
                        and contract.status != 'quote':
                    if activation_history['end_date']:
                        definition = termination
                    else:
                        definition = reactivate
                    endorsement = {
                            'effective_date': activation_history['end_date'],
                            'definition': definition.id,
                            'state': 'draft',
                            'contract_endorsements': [('create', [{
                                'contract': contract.id,
                                'activation_history': [('create', [{
                                    'action': 'update',
                                    'relation': history.id,
                                    'values': {
                                        'end_date':
                                        activation_history['end_date'],
                                        }}])],
                                    }])],
                            }
                    Endorsement.create([endorsement])
                else:
                    return [('write', [history.id], activation_history)]
        return None

    # @classmethod
    # def update_covered_elements(cls, contract, contract_lines):
    #     to_update = []
    #     to_create = []
    #     for line in contract_lines:
    #         covered_element = cls.init_covered_from_row(line)
    #         covered_elements = [covered.id
    #                 for covered in contract.covered_elements
    #                 if covered.contract.id == line['contract']
    #                 and covered.contract.id == line['contract'].id]
    #         if covered_elements:
    #             to_update.append(('write', covered_elements, covered_element))
    #         else:
    #             to_create.append(covered_element)
    #     return [('create', to_create)] + to_update

    @classmethod
    def _group_by_population(cls, line):
        return (line['code'], line['item_desc'])

    @classmethod
    def init_options_from_row(cls, contract_lines):
        contract_lines = sorted(contract_lines, key=cls._group_by_population)
        covered_elements = []
        ItemDesc = Pool().get('offered.item.description')
        for key, rows in groupby(contract_lines, key=cls._group_by_population):
            rows = list(rows)
            item_desc, = ItemDesc.search([('code', '=', key[1])])
            if item_desc.kind == 'subsidiary':
                continue
            parent_covered = cls.init_covered_from_row(rows[0])
            options = []
            for option_row in rows:
                item_desc = cls.cache_obj['item_desc'][option_row['item_desc']]
                coverage = cls.cache_obj['coverage'][option_row['coverage']]
                option = {
                    'item_desc': item_desc.id,
                    'manual_start_date': option_row['start_date'],
                    'manual_end_date': option_row['end_date'],
                    'coverage': coverage.id,
                    'versions': [
                        ('create', [{'start': option_row['start_date']}])]
                    }
                options.append(option)
            parent_covered['options'] = [('create', options)]
            covered_elements.append(parent_covered)
        return covered_elements

    @classmethod
    def _get_contract_exta_data(cls, contract_lines):
        for line in contract_lines:
            if line['extra_data']:
                return eval(line['extra_data'])
        return {}

    @classmethod
    def populate(cls, keys, contract_lines):
        contract = {}
        main_contract = contract_lines[0]
        contract['product'] = cls.cache_obj['product'][
            main_contract['product']].id
        contract['subscriber'] = cls.cache_obj['party'][keys[1]].id
        contract['contract_number'] = keys[0]
        contract['quote_number'] = keys[0]
        contract['company'] = cls.cache_obj['company'][1].id
        contract['current_state'] = cls.cache_obj['process_step'].id
        activation_history = cls.create_activation_history(contract_lines)
        start_date = min([d['start_date'] for d in contract_lines])
        if cls.do_update(contract['contract_number']):
            # TODO
            pass
            # existing = cls.cache_obj['update'][contract['contract_number']]
            # history_val = cls.create_endorsement(existing, activation_history)
            # if history_val:
            #     contract['activation_history'] = history_val
            # contract['covered_elements'] = cls.update_covered_elements(
            #     existing, contract_lines)
        else:
            contract['status'] = 'quote'  # only set status when not updating
            options = cls.init_options_from_row(
                [line for line in contract_lines if line['coverage']])
            contract['covered_elements'] = [('create', options)]
            extra_data = cls._get_contract_exta_data(contract_lines)
            if extra_data:
                contract['extra_datas'] = [('create', [{
                                'extra_data_values': extra_data,
                                'date': start_date,
                                }])]
            contract['activation_history'] = [('create', [activation_history])]
        return contract

    @classmethod
    def group_func(cls, x):
        return (x['contract_number'], x['party'], x['item_desc'])

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        to_upsert = {}
        ItemDesc = Pool().get('offered.item.description')
        for keys, contract_rows in groupby(rows, key=cls.group_func):
            item_desc, = ItemDesc.search([('code', '=', keys[2])])
            if item_desc.kind == 'subsidiary':
                continue
            row = cls.populate(keys, list(contract_rows))
            key = ':'.join(keys)
            to_upsert[key] = row
        if to_upsert:
            cls.upsert_records(to_upsert.values(), **kwargs)
        return to_upsert

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorContractGroup, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = []
        ItemDesc = Pool().get('offered.item.description')
        for r in res:
            item_desc = ItemDesc(
                res[r]['covered_elements'][0][1][0]['item_desc'])
            ids.append((
                    res[r]['contract_number'],
                    item_desc.code,
                    ))
        clause = Column(cls.table, cls.func_key).in_([x[0] for x in ids]
            ) & Column(cls.table, 'item_desc').in_([x[1] for x in ids])
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)


class MigratorContractSubsidiary(BaseMigratorContractGroup):
    'Migrate Contracts Subsidiaries'
    __name__ = 'migrator.contract.subsidiary'

    @classmethod
    def __setup__(cls):
        super(MigratorContractSubsidiary, cls).__setup__()
        cls.model = 'contract.covered_element'

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorContractSubsidiary, cls).init_cache(rows, **kwargs)
        CoveredElement = Pool().get('contract.covered_element')
        # TODO: Optimize ?
        cls.cache_obj['covered_element'] = {}
        cls.cache_obj['contract'] = tools.cache_from_search(
            'contract', 'contract_number',
            ('contract_number', 'in', [r['contract_number'] for r in rows]))

        for row in rows:
            if cls.cache_obj['item_desc'][row['item_desc']].kind != \
                    'subsidiary':
                continue
            parent_key = ':'.join(
                [row['contract_number'], row['coverage'] or '', row['code']])
            contract = cls.cache_obj['contract'][row['contract_number']].id
            parent_code = row['code']
            coverage = cls.cache_obj['coverage'][row['coverage']].id \
                if row['coverage'] else None
            parent_clause = [('contract', '=', contract)]
            if coverage:
                parent_clause.append(('coverage', '=', coverage))
            parent_covereds = CoveredElement.search(parent_clause)
            for parent_covered in parent_covereds:
                if parent_covered.name == parent_code or parent_code in \
                        parent_covered.current_extra_data.values():
                    cls.cache_obj['covered_element'][
                        parent_key] = parent_covered.id
                    break
            else:
                assert False, "Parent covered not found with code %s (%s)" % (
                    parent_code, parent_key)

    @classmethod
    def init_covered_from_row(cls, row):
        res = super(MigratorContractSubsidiary, cls).init_covered_from_row(row)
        parent_key = ':'.join([row['contract_number'], row['coverage'] or '',
                    row['code']])
        res['contract'] = cls.cache_obj['contract'][
            row['contract_number']]
        res['parent'] = cls.cache_obj['covered_element'][
            parent_key]
        res['party'] = cls.cache_obj['party'][row['party']]
        return res

    @classmethod
    def populate(cls, row):
        if cls.do_update(row['contract_number']):
            # TODO
            return {}
        else:
            return cls.init_covered_from_row(row)

    @classmethod
    def group_func(cls, x):
        return (
            x['contract_number'], x['code'], x['coverage'], x['party'],
            x['item_desc'])

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        to_upsert = {}
        ItemDesc = Pool().get('offered.item.description')
        for keys, contract_rows in groupby(rows, key=cls.group_func):
            item_desc, = ItemDesc.search([('code', '=', keys[4])])
            if item_desc.kind != 'subsidiary':
                continue
            contract_rows = list(contract_rows)
            assert len(contract_rows) == 1
            row = cls.populate(contract_rows[0])
            key = ':'.join([x or '' for x in keys])
            to_upsert[key] = row
        if to_upsert:
            cls.upsert_records(to_upsert.values(), **kwargs)
        return to_upsert

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorContractSubsidiary, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = []
        ItemDesc = Pool().get('offered.item.description')
        for r in res:
            item_desc = ItemDesc(res[r]['item_desc'])
            ids.append((
                    res[r]['contract'].contract_number,
                    item_desc.code,
                    ))
        clause = Column(cls.table, cls.func_key).in_([x[0] for x in ids]
            ) & Column(cls.table, 'item_desc').in_([x[1] for x in ids])
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)

    @classmethod
    def select(cls, **kwargs):
        select_keys = [
            Column(cls.table, 'contract_number'),
            Column(cls.table, 'party'),
            ]
        select = cls.table.select(*select_keys)
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        for row in rows:
            ids.append('{}_{}'.format(
                row.get('contract_number'),
                row.get('party'),
                ))
        return set(ids)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        table_name = cls.model.replace('.', '_')
        existing_ids = tools.cache_from_query(table_name,
            ('contract', 'party')).keys()
        pool = Pool()
        Contract = pool.get('contract')
        Party = pool.get('party.party')
        contracts = [x.contract_number for x in Contract.search(
                [('id', 'in', [x[0] for x in existing_ids])])]
        parties = [x.code for x in Party.search(
                [('id', 'in', [x[1] for x in existing_ids])])]
        existing_ids = {'%s_%s' % (x[0], x[1]) for x in zip(contracts, parties)}
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def query_data(cls, ids):
        ids = [x.split('_')[0] for x in ids]
        return super(MigratorContractSubsidiary, cls).query_data(ids)


class MigratorSubsidiaryAffiliated(Migrator):
    'Migrate Adhesions With Subsidiaries'
    __name__ = 'migrator.affiliated'

    @classmethod
    def __setup__(cls):
        super(MigratorSubsidiaryAffiliated, cls).__setup__()
        cls.table = Table('affiliated')
        cls.model = 'contract.covered_element'
        cls.func_key = 'uid'
        cls.columns = {
            'contract': 'contract',
            'population': 'population',
            'coverage': 'coverage',
            'company': 'company',
            'person': 'person',
            'start': 'start',
            'end': 'end',
            'end_reason': 'end_reason',
            'extra_data': 'extra_data',
            }

    @classmethod
    def init_cache(cls, rows, **kwargs):
        cls.cache_obj['person'] = tools.cache_from_search(
            'party.party', 'code',
            ('code', 'in', [r['person'] for r in rows]))
        cls.cache_obj['company'] = tools.cache_from_search(
            'party.party', 'code',
            ('code', 'in', [r['company'] for r in rows]))
        cls.cache_obj['end_reason'] = tools.cache_from_search(
            'covered_element.end_reason', 'code')
        cls.cache_obj['contract'] = tools.cache_from_search(
            'contract', 'contract_number', ('contract_number', 'in',
                [row['contract'] for row in rows]))
        cls.cache_obj['item_desc'] = tools.cache_from_search(
            'offered.item.description', 'code', ('code', '=', 'personne'))
        cls.cache_obj['coverage'] = tools.cache_from_search(
            'offered.option.description', 'code',
            ('code', 'in', [r['coverage'] for r in rows]))
        super(MigratorSubsidiaryAffiliated, cls).init_cache(rows, **kwargs)

    @classmethod
    def init_update_cache(cls, rows):
        pool = Pool()
        cursor = Transaction().connection.cursor()
        cls.cache_obj['update'] = {}
        parties = [cls.cache_obj['person'][row['person']].id for row in rows]
        companies = [cls.cache_obj['company'][row['company']].id
            for row in rows]
        contracts = [cls.cache_obj['contract'][row['contract']].id
            for row in rows]
        populations = [row['population'] for row in rows]
        if not parties or not companies or not contracts or not populations:
            return
        CoveredElement = pool.get('contract.covered_element')
        covered_person = CoveredElement.__table__()
        covered_parent = CoveredElement.__table__()
        covered_parent_parent = CoveredElement.__table__()
        option = pool.get('contract.option').__table__()

        query_table = covered_person.join(covered_parent, condition=(
                covered_person.parent == covered_parent.id)
            ).join(covered_parent_parent, condition=(
                covered_parent.parent == covered_parent_parent.id)
            ).join(option, condition=(
                option.covered_element == covered_parent_parent.id))

        where_clause = (covered_person.contract.in_(contracts) &
            covered_parent.party.in_(companies) &
            covered_person.party.in_(parties) &
            covered_parent_parent.name.in_(populations))

        query = query_table.select(covered_person.id, where=where_clause)
        cursor.execute(*query)

        update = {}
        existing_covereds = CoveredElement.browse(
            [x[0] for x in cursor.fetchall()])
        for covered in existing_covereds:
            uid = ':'.join(
                [covered.party.code, str(covered.parent.id)])
            update[uid] = covered
        cls.cache_obj['update'] = update

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorSubsidiaryAffiliated, cls).sanitize(row)
        row['manual_start_date'] = datetime.datetime.strptime(
            row['start'], '%Y-%m-%d')
        if row['end']:
            row['end'] = datetime.datetime.strptime(
                row['end'], '%Y-%m-%d')
        return row

    @classmethod
    def populate(cls, row):
        row['contract'] = cls.cache_obj['contract'][row['contract']]
        coverage = row['coverage']
        if coverage:
            coverage = cls.cache_obj['coverage'][row['coverage']].id
        parent_search = [
            ('party', '=', cls.cache_obj['company'][row['company']].id),
            ('contract', '=', row['contract'].id),
            ]
        if coverage:
            parent_search += [('parent.all_options.coverage', '=', coverage)]
        parent_covered, = Pool().get('contract.covered_element').search(
            parent_search, limit=1)
        row['parent'] = parent_covered
        row['party'] = cls.cache_obj['person'][row['person']]
        row['manual_end_date'] = row['end']
        row['uid'] = ':'.join([row['person'], str(row['parent'])])
        if row['end']:
            row['end_reason'] = cls.cache_obj['end_reason'][row['end_reason']]
        else:
            row['end_reason'] = None
        row['item_desc'] = cls.cache_obj['item_desc']['personne']
        if row['extra_data']:
            row['versions'] = [
                ('create', [{'extra_data': eval(row['extra_data'])}])]
        return row

    @classmethod
    def select(cls, **kwargs):
        select = cls.table.select(
            *[Column(cls.table, x) for x in cls.columns.keys()])
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        cls.init_cache(rows)
        for row in rows:
            # TODO: optimize
            coverage = row['coverage']
            if coverage:
                coverage = cls.cache_obj['coverage'][row['coverage']].id
            contract = cls.cache_obj['contract'][row['contract']].id
            parent_search = [
                ('party', '=', cls.cache_obj['company'][row['company']].id),
                ('contract', '=', contract),
                ]
            if coverage:
                parent_search += [
                    ('parent.all_options.coverage', '=', coverage)]
            parent_covered, = Pool().get('contract.covered_element').search(
                parent_search, limit=1)
            ids.append('{}_{}'.format(
                row.get('person'),
                parent_covered.id,
                ))
        return set(ids)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        table_name = cls.model.replace('.', '_')
        existing_ids = tools.cache_from_query(table_name,
            ('party', 'parent')).keys()
        existing_ids = {
            '%s_%s' % (party, parent) for party, parent in existing_ids}
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def query_data(cls, ids):
        Covered = Pool().get('contract.covered_element')
        where_clause = Literal(False)
        for id_ in ids:
            person, parent_covered_id = id_.split('_')
            parent_covered = Covered(int(parent_covered_id))
            company_code = parent_covered.party.code
            contract = parent_covered.contract.contract_number
            # TODO: Handle population properly in where clause
            where_clause |= (
                (cls.table.person == person) &
                (cls.table.company == company_code) &
                (cls.table.contract == contract)
                )

        select = cls.table.select(*cls.select_columns(),
            where=where_clause)
        return select

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorSubsidiaryAffiliated, cls).migrate(ids, **kwargs)
        if not res:
            return []

        ids = [(res[r]['party'].code, res[r]['parent'].party.code,
                res[r]['parent'].contract.contract_number) for r in res]
        clause = Literal(False)
        for id_ in ids:
            clause |= ((cls.table.person == id_[0]) &
                (cls.table.company == id_[1]) &
                (cls.table.contract == id_[2])
                )
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)


class MigratorContractGroupConfiguration(Migrator):
    'Migrate Contracts Groups Configuration'
    __name__ = 'migrator.contract.group.configuration'

    @classmethod
    def __setup__(cls):
        super(MigratorContractGroupConfiguration, cls).__setup__()
        cls.table = Table('contracts_configuration')
        cls.model = 'contract.option.benefit'
        cls.func_key = 'uid'
        cls.columns = {
            'contract_number': 'contract_number',
            'coverage': 'coverage',
            'population': 'population',
            'start_date': 'start_date',
            'benefit': 'benefit',
            'salary_mode': 'salary_mode',
            'net_calculation_rule': 'net_calculation_rule',
            'deductible_rule': 'deductible_rule',
            'deductible_rule_extra_data': 'deductible_rule_extra_data',
            'indemnification_rule': 'indemnification_rule',
            'indemnification_rule_extra_data':
            'indemnification_rule_extra_data',
            'revaluation_rule': 'revaluation_rule',
            'revaluation_rule_extra_data':
            'revaluation_rule_extra_data',
            'revaluation_on_basic_salary': 'revaluation_on_basic_salary',
            }

    @classmethod
    def _select_exisiting_benefits_query(cls, rows):
        pool = Pool()
        contract = pool.get('contract').__table__()
        covered_element = pool.get('contract.covered_element').__table__()
        option = pool.get('contract.option').__table__()
        version = pool.get('contract.option.version').__table__()
        Benefit = pool.get('contract.option.benefit')
        benefit_configuration = pool.get('benefit').__table__()
        coverage = pool.get('offered.option.description').__table__()
        cursor = Transaction().connection.cursor()
        cls.cache_obj['update'] = {}
        benefit = Benefit.__table__()

        query_table = contract.join(covered_element, condition=(
                covered_element.contract == contract.id)
            ).join(option, condition=(
                option.covered_element == covered_element.id)
            ).join(version, condition=(
                version.option == option.id)
            ).join(benefit, condition=(
                benefit.version == version.id)
            ).join(benefit_configuration, condition=(
                benefit.benefit == benefit_configuration.id)
            ).join(coverage, condition=(
                option.coverage == coverage.id))

        clause = Literal(False)
        for row in rows:
            clause |= (
                (contract.contract_number == row['contract_number']) &
                (version.start == row['start_date']) &
                (coverage.code == row['coverage']) &
                (benefit_configuration.code == row['benefit'])
                )

        cursor.execute(*query_table.select(benefit.id,
                contract.contract_number, covered_element.id,
                benefit_configuration.code, coverage.code, version.start,
                where=clause))
        return cursor.fetchall()

    @classmethod
    def init_update_cache(cls, rows):
        Benefit = Pool().get('contract.option.benefit')
        cls.cache_obj['update'] = {}

        update = {}

        for benefit_id, contract, covered_element, benefit_code, \
                coverage_code, start_date in \
                cls._select_exisiting_benefits_query(rows):
            uid = ':'.join([benefit_code, contract, str(covered_element),
                    coverage_code,
                    start_date.strftime('%Y-%m-%d') if start_date else ''])
            update[uid] = Benefit(benefit_id)
        cls.cache_obj['update'] = update

    @classmethod
    def init_cache(cls, rows, **kwargs):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        Version = pool.get('contract.option.version')
        NetRule = pool.get('claim.net_calculation_rule')
        coverage_codes = [r['coverage'] for r in rows]
        contract_numbers = [r['contract_number'] for r in rows]
        cls.cache_obj['contract'] = tools.cache_from_search('contract',
            'contract_number', ('contract_number', 'in', contract_numbers))
        cls.cache_obj['coverage'] = tools.cache_from_search(
            'offered.option.description', 'code', ('code', 'in',
                coverage_codes))
        cls.cache_obj['benefit'] = tools.cache_from_search(
            'benefit', 'code', ('code', 'in',
                [r['benefit'] for r in rows]))
        cls.cache_obj['deductible_rule'] = tools.cache_from_search(
            'rule_engine', 'short_name', ('short_name', 'in',
                [r['deductible_rule'] for r in rows]))
        cls.cache_obj['indemnification_rule'] = tools.cache_from_search(
            'rule_engine', 'short_name', ('short_name', 'in',
                [r['indemnification_rule'] for r in rows]))
        cls.cache_obj['revaluation_rule'] = tools.cache_from_search(
            'rule_engine', 'short_name', ('short_name', 'in',
                [r['revaluation_rule'] for r in rows]))
        net_calculation_rules = NetRule.search([
                ('rule.short_name', 'in',
                    [r['net_calculation_rule'] for r in rows])
                ])
        cls.cache_obj['net_calculation_rule'] = {}
        for net_rule in net_calculation_rules:
            cls.cache_obj['net_calculation_rule'][net_rule.rule.short_name] = \
                net_rule
        versions = Version.search([
                ('option.coverage.code', 'in', coverage_codes),
                ('option.covered_element.contract.contract_number', 'in',
                    contract_numbers),
                ])
        cls.cache_obj['version'] = {}
        for version in versions:
            version_key = ':'.join([
                    version.option.covered_element.contract.contract_number,
                    version.option.covered_element.name or '',
                    version.option.coverage.code,
                    version.start_date.strftime('%Y-%m-%d')
                    if version.start else '',
                    ])
            cls.cache_obj['version'][version_key] = version
        cls.cache_obj['covered_element'] = {}
        for row in rows:
            parent_code = row['population']
            parent_key = ':'.join(
                [row['contract_number'], row['coverage'] or '',
                    parent_code])
            contract = cls.cache_obj['contract'][row['contract_number']].id
            coverage = cls.cache_obj['coverage'][row['coverage']].id \
                if row['coverage'] else None
            parent_clause = [
                ('contract', '=', contract),
                ('options.coverage', '=', coverage),
                ]
            parent_covereds = CoveredElement.search(parent_clause)
            # TODO: Handle population properly

            for parent_covered in parent_covereds:
                if parent_covered.name == parent_code or parent_code in \
                        parent_covered.current_extra_data.values():
                    cls.cache_obj['covered_element'][
                        parent_key] = parent_covered
                    break
            else:
                assert False, "Parent covered not found with code %s (%s)" % (
                    parent_code, parent_key)

        super(MigratorContractGroupConfiguration, cls).init_cache(
            rows, **kwargs)

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorContractGroupConfiguration, cls).sanitize(row)
        row['start_date'] = datetime.datetime.strptime(
            row['start_start'], '%Y-%m-%d').date() \
            if row['start_date'] else None
        row['deductible_rule_extra_data'] = eval(
            row['deductible_rule_extra_data'])
        row['indemnification_rule_extra_data'] = eval(
            row['indemnification_rule_extra_data'])
        row['revaluation_rule_extra_data'] = eval(
            row['revaluation_rule_extra_data'])
        row['revaluation_on_basic_salary'] = bool(
            row['revaluation_on_basic_salary'])
        return row

    @classmethod
    def populate(cls, row):
        benefit = cls.cache_obj['benefit'][row['benefit']]
        contract = cls.cache_obj['contract'][row['contract_number']]
        parent_key = ':'.join([row['contract_number'], row['coverage'] or '',
                    row['population']])
        covered_element = cls.cache_obj['covered_element'][parent_key]
        start_date = row['start_date']
        uid = ':'.join([row['benefit'], contract.contract_number,
                str(covered_element.id), row['coverage'],
                start_date.strftime('%Y-%m-%d') if start_date else ''])
        row['uid'] = uid
        version_key = ':'.join([
                contract.contract_number,
                covered_element.name or '',
                row['coverage'],
                start_date.strftime('%Y-%m-%d') if start_date else '',
                ])
        row['version'] = cls.cache_obj['version'][version_key]
        row['deductible_rule'] = cls.cache_obj['deductible_rule'][
                row['deductible_rule']]
        row['indemnification_rule'] = cls.cache_obj['indemnification_rule'][
                row['indemnification_rule']]
        row['revaluation_rule'] = cls.cache_obj['revaluation_rule'][
                row['revaluation_rule']]
        row['benefit'] = benefit
        row['net_calculation_rule'] = cls.cache_obj['net_calculation_rule'][
            row['net_calculation_rule']] if row['net_calculation_rule'] else \
            None
        row['net_salary_mode'] = bool(row['net_calculation_rule'])
        return row

    @classmethod
    def select(cls, **kwargs):
        select = cls.table.select(
            *[Column(cls.table, x) for x in cls.columns.keys()])
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        cls.init_cache(rows)
        for row in rows:
            covered_key = ':'.join([
                    row['contract_number'], row['coverage'] or '',
                    row['population'],
                    ])
            covered = cls.cache_obj['covered_element'][covered_key]
            ids.append('{}|{}|{}|{}|{}'.format(
                    row['benefit'],
                    row['contract_number'],
                    str(covered.id),
                    row['coverage'],
                    row['start_date'] or '',
                    ))
        return set(ids)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        rows = []
        for id_ in ids:
            row = id_.split('|')
            rows.append({
                    'contract_number': row[1],
                    'start_date': datetime.datetime.strptime(row[4],
                        '%Y-%m-%d').date() if row[4] else None,
                    'coverage': row[3],
                    'benefit': row[0],
                    })
        existing_ids = {'|'.join([
                    r[3], r[1], str(r[2]), r[4], r[5] if r[5] else ''
                    ]) for r in cls._select_exisiting_benefits_query(rows)}
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def query_data(cls, ids):
        where_clause = Literal(False)
        for id_ in ids:
            benefit_code, contract_number, covered_id, coverage, start_date = \
                id_.split('|')
            # TODO: Handle population properly in where clause
            where_clause |= (
                (cls.table.benefit == benefit_code) &
                (cls.table.contract_number == contract_number) &
                (cls.table.coverage == coverage) &
                (cls.table.start_date == (start_date if start_date else Null)
                ))
        select = cls.table.select(*cls.select_columns(),
            where=where_clause)
        return select

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorContractGroupConfiguration, cls).migrate(
            ids, **kwargs)
        if not res:
            return []
        ids = [(res[r]['benefit'].code, res[r]['version'].option.coverage.code,
                res[r]['version'
                    ].option.covered_element.contract.contract_number,
                res[r]['version'].start or None) for r in res]
        clause = Literal(False)
        for benefit_code, coverage_code, contract_number, start_date in ids:
            clause |= ((cls.table.benefit == benefit_code) &
                (cls.table.coverage == coverage_code) &
                (cls.table.contract_number == contract_number) &
                (cls.table.start_date == (start_date or Null)))
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)
        return res
