# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime
from decimal import Decimal
from itertools import groupby
from dateutil.relativedelta import relativedelta

from sql import Table, Column, Literal

from trytond.pool import Pool

from trytond.modules.migrator import Migrator, tools
from trytond.modules.coog_core import coog_date
from trytond.modules.coog_core import batch


__all__ = [
    'MigratorClaim',
    'MigratorClaimIndemnification',
    ]


class MigratorClaim(Migrator):
    'Migrator Claim'
    __name__ = 'migrator.claim'

    @classmethod
    def __setup__(cls):
        super(MigratorClaim, cls).__setup__()
        cls.table = Table('claims')
        cls.model = 'claim'
        cls.func_key = 'uid'
        cls.columns = {
            'name': 'name',
            'contract': 'contract',
            'covered_person': 'covered_person',
            'event_desc': 'event_desc',
            'declaration_date': 'declaration_date',
            'start_date': 'start_date',
            'end_date': 'end_date',
            'closing_reason': 'closing_reason',
            'gross_salary': 'gross_salary',
            'net_salary': 'net_salary',
            'coverage': 'coverage',
            'benefit': 'benefit',
            'loss_desc': 'loss_desc',
            'loss_extra_data': 'loss_extra_data',
            'line_kind': 'line_kind',
            'part_time_amount': 'part_time_amount',
            'sub_status': 'sub_status',
            'deductible': 'deductible',
            }

    @classmethod
    def init_update_cache(cls, rows):
        ids = set([row[cls.func_key] for row in rows])
        claims = tools.cache_from_search('claim', 'name', ('name', 'in', ids))
        update = {}
        for claim in claims:
            for service in claim.delivered_services:
                key = ':'.join(claim.name, service.loss.loss_desc.code,
                    claim.serice.loss.covered_person.code)
                update[key] = claim.service
        cls.cache_obj['update'] = update

    @classmethod
    def init_cache(cls, rows, **kwargs):
        pool = Pool()
        CoveredElement = pool.get('contract.covered_element')
        cls.cache_obj['claim'] = {}
        cls.cache_obj['contract'] = tools.cache_from_search('contract',
            'contract_number',
            ('contract_number', 'in', [r['contract'] for r in rows]))
        cls.cache_obj['event_description'] = tools.cache_from_search(
            'benefit.event.description', 'code',
            ('code', 'in', [r['event_desc'] for r in rows]))
        cls.cache_obj['covered_person'] = tools.cache_from_search(
            'party.party', 'code',
            ('code', 'in', [r['covered_person'] for r in rows]))
        cls.cache_obj['event_description'] = tools.cache_from_search(
            'benefit.event.description', 'code',
            ('code', 'in', [r['event_desc'] for r in rows]))
        cls.cache_obj['closing_reason'] = tools.cache_from_search(
            'claim.closing_reason', 'code',
            ('code', 'in', [r['closing_reason'] for r in rows]))
        cls.cache_obj['loss_desc'] = tools.cache_from_search(
            'benefit.loss.description', 'code',
            ('code', 'in', [r['loss_desc'] for r in rows]))
        cls.cache_obj['sub_status'] = tools.cache_from_search(
            'claim.sub_status', 'code',
            ('code', 'in', [r['sub_status'] for r in rows]))
        cls.cache_obj['deduction_kind'] = tools.cache_from_search(
            'benefit.loss.description.deduction_period_kind', 'code',
            ('code', 'in', [r['line_kind'] for r in rows if r['line_kind']]))
        cls.cache_obj['eligibility_decision_default'], = pool.get(
            'benefit.eligibility.decision').search(
            [('code', '=', batch._config.get(
                cls.__name__, 'eligibility_decision'))], limit=1)
        covered_elements = {}
        for row in rows:
            all_covered = CoveredElement.search([
                    ('party', '=', cls.cache_obj['covered_person'][
                        row['covered_person']].id),
                    ('contract', '=', cls.cache_obj['contract'][
                        row['contract']].id),
                    ])
            all_covered = [x for x in all_covered if
                x.start_date <= row['start_date']]
            all_covered = [x for x in all_covered if not x.end_date or
                (x.end_date >= row['start_date'])]
            if not all_covered:
                raise Exception(
                    'NO COVERED FOR %s - %s' % (row['contract'],
                        row['covered_person']))
            all_covered = sorted(all_covered, key=lambda x: x.start_date)
            covered_element = all_covered[-1]
            key = ':'.join([row['covered_person'], row['contract']])
            covered_elements[key] = covered_element
        cls.cache_obj['covered_element'] = covered_elements
        super(MigratorClaim, cls).init_cache(rows, **kwargs)

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorClaim, cls).sanitize(row)
        row['declaration_date'] = datetime.datetime.strptime(
            row['declaration_date'], '%Y-%m-%d').date()
        row['start_date'] = datetime.datetime.strptime(row['start_date'],
            '%Y-%m-%d').date()
        row['end_date'] = datetime.datetime.strptime(row['end_date'],
            '%Y-%m-%d').date() if row['end_date'] else None
        row['gross_salary'] = Decimal(row['gross_salary']) if \
            row['gross_salary'] else Decimal('0')
        row['net_salary'] = Decimal(row['net_salary']) if \
            row['net_salary'] else Decimal('0')
        row['deductible'] = int(row['deductible']) if row['deductible'] else 0
        return row

    @classmethod
    def _set_salary(cls, service, row):
        service.init_salaries()
        if row['gross_salary'] or row['net_salary']:
            service.salary[0].gross_salary = row['gross_salary']
            service.salary[0].net_salary = row['net_salary']
            service.salary[0].save()
        return service

    @classmethod
    def _create_services(cls, loss, options, row):
        services = []
        pool = Pool()
        Service = pool.get('claim.service')
        for option in options:
            benefits = [(benefit_option.benefit, benefit_option)
                    for benefit_option in option.current_version.benefits
                    if benefit_option.benefit.code == row['benefit']]
            if not benefits:
                raise Exception(
                    'No benefits for claim %s' % row['name'])
            for benefit, benefit_option in benefits:
                if loss.loss_desc not in benefit.loss_descs:
                    continue
                service = Service()
                service.option = option
                service.contract = option.parent_contract
                service.salary_mode = benefit_option.salary_mode
                service.loss = loss
                service.eligibility_status = 'accepted'
                service.benefit = benefit
                service.annuity_frequency = \
                    benefit.benefit_rules[0].annuity_frequency
                service.on_change_extra_datas()
                service.specific_salary_mode = 'last_year'
                # Cannot do without the following save
                service.save()
                if len(loss.claim.losses) == 1 and loss.loss_kind in (
                        'std', 'ltd'):
                    service = cls._set_salary(service, row)
                loss.services += (service,)
                services.append(service)
                if row['deductible']:
                    cls._create_deductible_period(row, service,
                        row['deductible'])
        return services

    @classmethod
    def _death_loss(cls, claim, date):
        for loss in claim.losses:
            if loss.loss_kind == 'death' and loss.start_date == date:
                return loss
        return None

    @classmethod
    def _create_loss(cls, claim, options, row):
        Service = Pool().get('claim.service')
        exisiting_death_loss = cls._death_loss(claim, row['start_date'])
        loss_desc = cls.cache_obj['loss_desc'][row['loss_desc']]
        if not (exisiting_death_loss and loss_desc.loss_kind == 'death'):
            loss = Pool().get('claim.loss')()
            loss.claim = claim
            loss_params = {}
            loss_params['is_a_relapse'] = row['line_kind'] == 'relapse'
            if loss_params['is_a_relapse']:
                loss.relapse_initial_loss = claim.loss[0]
            loss_params['start_date'] = row['start_date']
            loss_params['end_date'] = row['end_date']
            if row['end_date']:
                loss.closing_reason = cls.cache_obj['closing_reason'][
                    row['closing_reason']]
            loss_params['state'] = 'active'
            loss_desc_code = row['loss_desc']
            event_desc = cls.cache_obj['event_description'][row['event_desc']]
            loss_params['event_desc'] = event_desc
            loss.loss_kind = loss_desc.loss_kind
            if loss.loss_kind != 'ltd':
                loss.initial_std_start_date = None
            else:
                loss.initial_std_start_date = row['start_date']
            loss.init_loss(loss_desc_code, **loss_params)
            loss.extra_data = eval(row['loss_extra_data'] or '{}')
            loss.services = []
        else:
            loss = exisiting_death_loss
        if not options:
            raise Exception('No Options')
        services = cls._create_services(loss, options, row)
        loss.services = list(loss.services) + services
        for service in loss.services:
            service.specific_salary_mode = 'last_year'
        if services:
            Service.save(services)
        return loss

    @classmethod
    def get_available_options_from_covered(cls, covered):
        if covered.parent:
            return list(covered.options) + \
                cls.get_available_options_from_covered(covered.parent)
        return list(covered.options)

    @classmethod
    def _create_update_claim(cls, row, covered_element, init_claim=None):
        if init_claim:
            claim = init_claim
        else:
            claim = Pool().get('claim')()
            claim.name = row['name']
            claim.declaration_date = row['declaration_date']
            claim.losses = []
            claim.claimant = covered_element.party
            companies = claim.claimant.companies
            if companies:
                claim.legal_entity = companies[0].id
            sub_status = row.get('sub_status', '')
            status = 'open' if not sub_status else 'closed'
            claim.status = status
            if sub_status:
                claim.sub_status = cls.cache_obj['sub_status'][sub_status]
            if not claim.claimant:
                claim.legal_entity = None

        options = [x for x in cls.get_available_options_from_covered(
                covered_element) if x.coverage.code == row['coverage']]
        loss = cls._create_loss(claim, options, row)
        claim.losses = list(set(claim.losses + (loss,)))
        cls.cache_obj['claim'][claim.name] = claim
        return claim

    @classmethod
    def _create_part_time(cls, claim_line, claim):
        DeductionPeriod = Pool().get('claim.loss.deduction.period')
        assert claim, 'Invalid line order in migration file for %s' % \
            claim_line['name']
        period = DeductionPeriod()
        period.start_date = claim_line['start_date']
        period.end_date = claim_line['end_date']
        period.amount_received = claim_line['part_time_amount']
        period.amount_kind = 'total'
        period.deduction_kind = cls.cache_obj['deduction_kind'][
            claim_line['line_kind']]
        return period

    @classmethod
    def _create_deductible_details(cls, row, indemnification, deductible_days):
        details = {}
        details['kind'] = 'deductible'
        details['unit'] = 'day'
        details['start_date'] = indemnification['start_date']
        details['end_date'] = indemnification['end_date']
        details['nb_of_unit'] = deductible_days
        details['base_amount'] = Decimal('0')
        details['amount'] = Decimal('0')
        details['amount_per_unit'] = Decimal('0')
        details['extra_details'] = {
            'tranche_a': 0,
            'tranche_b': 0,
            'tranche_c': 0,
            'ijss': 0,
            }
        details['description'] = 'Migrated deductible data'
        return details

    @classmethod
    def _create_deductible_period(cls, indemn_row, service, deductible_days):
        indemn = {}
        indemn['service'] = service
        indemn['start_date'] = service.loss.start_date
        indemn['end_date'] = coog_date.add_day(service.loss.start_date,
            deductible_days)
        indemn['total_amount'] = Decimal('0')
        indemn['status'] = 'paid'
        indemn['beneficiary'] = cls.cache_obj['covered_person'][
            indemn_row['covered_person']]
        indemn['details'] = [('create', [cls._create_deductible_details(
                        indemn_row, indemn, deductible_days)])]
        indemn['possible_products'] = indemn['service'
            ].benefit.company_products
        if len(indemn['possible_products']) >= 1:
            indemn['product'] = indemn['possible_products'][0]
        return indemn

    @classmethod
    def populate(cls, keys, claim_lines):
        claim = None
        for claim_line in claim_lines:
            key = ':'.join([claim_line['covered_person'],
                    claim_line['contract']])
            covered_element = cls.cache_obj['covered_element'][key]
            if not claim_line['line_kind'] or claim_line['line_kind'] == \
                    'relapse':
                claim = cls._create_update_claim(claim_line,
                    covered_element, claim)
            elif claim_line['line_kind'] == 'part_time':
                deduction = cls._create_part_time(claim_line, claim)
                deduction.loss = claim.losses[-1]
                claim.losses[-1].deduction_periods = [deduction] + \
                    list(claim.losses[-1].deduction_periods or [])
            else:
                raise NotImplementedError(claim_line['line_kind'])
        assert all([x.specific_salary_mode == 'last_year']
                for x in claim.delivered_services)
        return claim

    @classmethod
    def group_func(cls, x):
        return (x['name'],)

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        Claim = Pool().get('claim')
        to_upsert = {}
        for keys, claim_rows in groupby(rows, key=cls.group_func):
            key, = keys
            claim = cls.populate(keys, list(claim_rows))
            to_upsert[key] = claim
        if to_upsert:
            Claim.save(list(to_upsert.values()))
        return to_upsert

    @classmethod
    def _group_by_claim_number(cls, id_):
        return id_.split(':')[0]

    @classmethod
    def select_group_ids(cls, ids):
        ids = sorted(ids, key=cls._group_by_claim_number)
        jobs = []
        for key, grouped_ids in groupby(ids, key=cls._group_by_claim_number):
            jobs.append([(x,) for x in grouped_ids])
        return jobs

    @classmethod
    def select(cls, **kwargs):
        select = cls.table.select(
            *[Column(cls.table, x) for x in list(cls.columns.keys())])
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        for row in rows:
            ids.append('{}:{}:{}'.format(
                row.get('name'),
                row.get('loss_desc'),
                row.get('covered_person')
                ))
        return ids

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        return ids

    @classmethod
    def query_data(cls, ids):
        where_clause = Literal(False)
        for id_ in ids:
            name, loss_desc, covered_person = id_.split(':')
            where_clause |= (
                (cls.table.name == name) &
                (cls.table.loss_desc == loss_desc) &
                (cls.table.covered_person == covered_person)
                )
        select = cls.table.select(*cls.select_columns(),
            where=where_clause)
        return select

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorClaim, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = []
        for key in res:
            for service in res[key].delivered_services:
                ids.append((service.claim.name, service.loss.loss_desc.code,
                    service.loss.covered_person.code))
        clause = Literal(False)
        for id_ in ids:
            clause |= ((cls.table.name == id_[0]) &
                (cls.table.loss_desc == id_[1]) &
                (cls.table.covered_person == id_[2])
                )
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)
        return res


class MigratorClaimIndemnification(Migrator):
    'Migrator Claim Indemnification'
    __name__ = 'migrator.claim.indemnification'

    @classmethod
    def __setup__(cls):
        super(MigratorClaimIndemnification, cls).__setup__()
        cls.table = Table('indemnifications')
        cls.model = 'claim.indemnification'
        cls.func_key = 'uid'
        cls.columns = {
            'claim_number': 'claim_number',
            'loss_kind': 'loss_kind',
            'party': 'party',
            'payment_date': 'payment_date',
            'journal': 'journal',
            'iban': 'iban',
            'total_amount': 'total_amount',
            'start_date': 'start_date',
            'end_date': 'end_date',
            'base_amount': 'base_amount',
            'tranche_a': 'tranche_a',
            'tranche_b': 'tranche_b',
            'tranche_c': 'tranche_c',
            'revaluation': 'revaluation',
            'ijss': 'ijss',
            }

    @classmethod
    def _find_services(cls, rows):
        Service = Pool().get('claim.service')
        clause = ['OR']
        for r in rows:
            clause.append([
                    ('claim.name', '=', r['claim_number']),
                    ('loss.loss_desc.code', '=', r['loss_kind'])
                    ])
        return Service.search(clause)

    @classmethod
    def init_update_cache(cls, rows):
        services = cls.cache_obj['service']
        update = {}
        for uid, service in services.items():
            update[uid] = service
        cls.cache_obj['update'] = update

    @classmethod
    def init_cache(cls, rows, **kwargs):
        super(MigratorClaimIndemnification, cls).init_cache(rows, **kwargs)
        cls.cache_obj['claim'] = tools.cache_from_search('claim', 'name',
            ('name', 'in', [r['claim_number'] for r in rows]))
        cls.cache_obj['journal'] = tools.cache_from_search(
            'account.payment.journal', 'name',
            ('name', 'in', [r['journal'] for r in rows]))
        cls.cache_obj['party'] = tools.cache_from_search(
            'party.party', 'code',
            ('code', 'in', [r['party'] for r in rows]))
        services = cls._find_services(rows)
        cls.cache_obj['service'] = {}
        for service in services:
            key = ':'.join([service.claim.name, service.loss.loss_desc.code])
            cls.cache_obj['service'][key] = service

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorClaimIndemnification, cls).sanitize(row)
        row['payment_date'] = datetime.datetime.strptime(
            row['payment_date'], '%Y-%m-%d').date() if row['payment_date'] \
            else None
        row['total_amount'] = Decimal(row['total_amount']) if \
            row['total_amount'] else Decimal('0')
        row['start_date'] = datetime.datetime.strptime(row['start_date'],
            '%Y-%m-%d').date()
        row['end_date'] = datetime.datetime.strptime(row['end_date'],
            '%Y-%m-%d').date()
        row['base_amount'] = Decimal(row['base_amount']) if \
            row['base_amount'] else Decimal('0')
        row['tranche_a'] = Decimal(row['tranche_a']) if \
            row['tranche_a'] else Decimal('0')
        row['tranche_b'] = Decimal(row['tranche_b']) if \
            row['tranche_b'] else Decimal('0')
        row['tranche_c'] = Decimal(row['tranche_c']) if \
            row['tranche_c'] else Decimal('0')
        row['revaluation'] = Decimal(row['revaluation']) if \
            row['revaluation'] else Decimal('0')
        row['ijss'] = Decimal(row['ijss']) if \
            row['ijss'] else Decimal('0')
        return row

    @classmethod
    def _create_details(cls, row, previous_date=None, description=None):
        details = {}
        details['kind'] = 'benefit'
        details['unit'] = 'day'
        details['start_date'] = previous_date or row['start_date']
        details['end_date'] = row['end_date'] if not previous_date else \
            row['start_date'] + relativedelta(days=-1)
        details['nb_of_unit'] = coog_date.number_of_days_between(
            details['start_date'], details['end_date'])
        details['base_amount'] = row['base_amount'] if not previous_date else \
            Decimal('0')
        details['amount'] = row['total_amount'] if not previous_date else \
             Decimal('0')
        details['amount_per_unit'] = (row['base_amount'] +
            row['revaluation']) if not previous_date else Decimal('0')
        details['amount_per_unit'] = Decimal(
            details['amount_per_unit']).quantize(Decimal("0.01"))
        details['extra_details'] = {
            'tranche_a': row['tranche_a'] if not previous_date else 0,
            'tranche_b': row['tranche_b'] if not previous_date else 0,
            'tranche_c': row['tranche_c'] if not previous_date else 0,
            'ijss': row['ijss'] if not previous_date else 0,
            }
        details['description'] = description or 'Migrated data'
        return details

    @classmethod
    def _set_extra_data(cls, service, value, date):
        if not value:
            value = Decimal('0.00')
        ExtraData = Pool().get('claim.service.extra_data')
        prev_extra_data = service.extra_datas[-1].extra_data_values
        if 'ijss' not in prev_extra_data or prev_extra_data['ijss'] is None:
            new_extra_data = prev_extra_data.copy()
            new_extra_data['ijss'] = value
            service.extra_datas[-1].extra_data_values = new_extra_data
        elif prev_extra_data['ijss'] != value:
            new_extra_data = prev_extra_data.copy()
            new_extra_data['ijss'] = value
            service.extra_datas += (ExtraData(
                    extra_data_values=new_extra_data,
                    date=date),)
        service.extra_datas = service.extra_datas
        service.save()

    @classmethod
    def _create_indemnification(cls, indemn_row, previous_date=None, desc=None):
        indemn = {}
        service_key = ':'.join([indemn_row['claim_number'],
                indemn_row['loss_kind']])
        service = cls.cache_obj['service'][service_key]
        indemn['service'] = service
        indemn['start_date'] = previous_date or indemn_row['start_date']
        indemn['end_date'] = indemn_row['end_date'] if not previous_date else \
            indemn_row['start_date'] + relativedelta(days=-1)
        indemn['total_amount'] = indemn_row['total_amount'] \
            if not previous_date else Decimal('0')
        indemn['status'] = 'paid'
        indemn['beneficiary'] = cls.cache_obj['party'][indemn_row['party']]
        indemn['details'] = [('create', [cls._create_details(indemn_row,
                        previous_date, desc)])]
        indemn['possible_products'] = indemn['service'
            ].benefit.company_products
        indemn['journal'] = cls.cache_obj['journal'][indemn_row['journal']]
        if len(indemn['possible_products']) >= 1:
            indemn['product'] = indemn['possible_products'][0]
        cls._set_extra_data(service, indemn_row['ijss'],
            indemn_row['start_date'])
        return indemn

    @classmethod
    def populate(cls, keys, indemn_row):
        return cls._create_indemnification(indemn_row)

    @classmethod
    def group_func(cls, x):
        return (x['claim_number'])

    @classmethod
    def migrate_rows(cls, rows, ids, **kwargs):
        to_upsert = {}
        for keys, indemn_rows in groupby(rows, key=cls.group_func):
            indemn_rows = sorted(indemn_rows, key=lambda x: x['start_date'])
            for idx, indemn_row in enumerate(indemn_rows):
                row = cls.populate(keys, indemn_row)
                uid = ':'.join([
                        indemn_row['claim_number'], indemn_row['loss_kind'],
                        indemn_row['start_date'].strftime('%Y-%m-%d')
                        ])
                to_upsert[uid] = row
                service_key = ':'.join([indemn_row['claim_number'],
                        indemn_row['loss_kind']])
                service = cls.cache_obj['service'][service_key]
                if idx > 0:
                    previous_date = indemn_rows[idx - 1]['end_date']
                else:
                    previous_date = service.loss.start_date
                # Fill gap with extra indemnification
                if previous_date and coog_date.number_of_days_between(
                        previous_date, indemn_row['start_date']) > (2
                        if idx > 0 else 1):
                    comment = None
                    if kwargs.get('auto_fill_period'):
                        comment = kwargs.get('auto_fill_comment', None)
                        fill_date = previous_date + relativedelta(days=1
                            if idx > 0 else 0)
                        fill_indemn = cls._create_indemnification(indemn_row,
                            fill_date, comment)
                        fill_uid = ':'.join([fill_indemn['service'].claim.name,
                                indemn_row['loss_kind'],
                                fill_date.strftime('%Y-%m-%d')])
                        to_upsert[fill_uid] = fill_indemn
        if to_upsert:
            cls.upsert_records(list(to_upsert.values()), **kwargs)
        return to_upsert

    @classmethod
    def _group_by_claim_number(cls, id_):
        return id_.split(':')[0]

    @classmethod
    def select_group_ids(cls, ids):
        ids = sorted(ids, key=cls._group_by_claim_number)
        jobs = []
        for key, grouped_ids in groupby(ids, key=cls._group_by_claim_number):
            jobs.append([(x,) for x in grouped_ids])
        return jobs

    @classmethod
    def select(cls, **kwargs):
        select = cls.table.select(
            *[Column(cls.table, x) for x in list(cls.columns.keys())])
        return select, cls.func_key

    @classmethod
    def select_extract_ids(cls, select_key, rows):
        ids = []
        for row in rows:
            ids.append('{}:{}:{}'.format(
                row.get('claim_number'),
                row.get('loss_kind'),
                row.get('start_date')
                ))
        return set(ids)

    @classmethod
    def select_remove_ids(cls, ids, excluded, **kwargs):
        pool = Pool()
        Claim = pool.get('claim')
        claims = Claim.search(
            [('name', 'in', [x.split(':')[0] for x in ids])])
        existing_ids = []
        for claim in claims:
            for indemn in claim.indemnifications:
                existing_ids.append('%s:%s:%s' % (
                        claim.name, indemn.service.loss.loss_desc.code,
                        indemn.start_date.strftime('%Y-%m-%d')))
        return list(set(ids) - set(excluded) - set(existing_ids))

    @classmethod
    def query_data(cls, ids):
        where_clause = Literal(False)
        for id_ in ids:
            name, loss_kind, start_date = id_.split(':')
            where_clause |= (
                (cls.table.claim_number == name) &
                (cls.table.loss_kind == loss_kind) &
                (cls.table.start_date == start_date)
                )
        select = cls.table.select(*cls.select_columns(),
            where=where_clause)
        return select

    @classmethod
    def migrate(cls, ids, **kwargs):
        res = super(MigratorClaimIndemnification, cls).migrate(ids, **kwargs)
        if not res:
            return []
        ids = [(res[r]['service'].claim.name,
                res[r]['service'].loss.loss_desc.code,
                res[r]['start_date'].strftime('%Y-%m-%d')) for r in res]
        clause = Literal(False)
        for id_ in ids:
            clause |= ((cls.table.claim_number == id_[0]) &
                (cls.table.loss_kind == id_[1]) &
                (cls.table.start_date == id_[2])
                )
        cls.delete_rows(tools.CONNECT_SRC, cls.table, clause)
        return res
