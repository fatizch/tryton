# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import datetime
from collections import defaultdict
from itertools import groupby

from sql import Table, Column

from trytond.modules.migrator import Migrator, tools
from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch

__all__ = [
    'MigratorContractGroup',
    'MigratorContractSubsidiary',
    'MigratorSubsidiaryAffiliated',
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
        ContractOption = Pool().get('contract.covered_element')
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
            parent_covereds = ContractOption.search(parent_clause)
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
        coverages = [cls.cache_obj['coverage'][row['coverage']].id
            for row in rows]
        if not parties or not companies or not contracts or not populations \
                or not coverages:
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

        query = query_table.select(covered_person.id, where=(
                covered_person.contract.in_(contracts) &
                covered_parent.party.in_(companies) &
                covered_person.party.in_(parties) &
                option.coverage.in_(coverages) &
                covered_parent_parent.name.in_(populations)
                ))
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
        row['contract'] = cls.cache_obj['contract'][row['contract']].id
        parent_covered, = Pool().get('contract.covered_element').search([
                ('party', '=', cls.cache_obj['company'][row['company']].id),
                ('contract', '=', row['contract']),
                ('parent.all_options.coverage', '=',
                    cls.cache_obj['coverage'][row['coverage']].id),
                ], limit=1)
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
            contract = cls.cache_obj['contract'][row['contract']].id
            parent_covered, = Pool().get('contract.covered_element').search([
                    ('party', '=', cls.cache_obj['company'][row['company']].id),
                    ('contract', '=', contract),
                    ('parent.all_options.coverage', '=',
                        cls.cache_obj['coverage'][row['coverage']].id),
                    ], limit=1)

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
        select = cls.table.select(*cls.select_columns())
        return select

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorSubsidiaryAffiliated, cls).migrate(ids, **kwargs)
        if not res:
            return []

        ids = [(res[r]['party'].code, res[r]['parent'].party.code,
                res[r]['parent'].contract.contract_number) for r in res]
        clause = Column(cls.table, 'person').in_([x[0] for x in ids]
            ) & Column(cls.table, 'company').in_([x[1] for x in ids]
            ) & Column(cls.table, 'contract').in_([x[2] for x in ids]
            )
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)
