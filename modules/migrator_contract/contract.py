# coding: utf-8

import datetime

from collections import defaultdict
from itertools import groupby, chain, tee, izip
from sql import Table

from trytond.pool import Pool

from trytond.modules.coog_core import coog_date
from trytond.modules.migrator import migrator, tools

__all__ = [
    'MigratorContract',
    'MigratorContractOption',
    'MigratorContractEvent',
    'MigratorContractPremium',
    'MigratorContractPremiumWaiver',
    'MigratorContractVersion'
]


class MigratorContractPremium(migrator.Migrator):
    """Migrator Contract Premium"""

    __name__ = 'migrator.contract.premium'

    @classmethod
    def __setup__(cls):
        super(MigratorContractPremium, cls).__setup__()
        cls.table = Table('premium')
        cls.model = 'contract.premium'
        cls.columns = {k: k for k in ('id', 'amount', 'contract',
            'covered_element', 'start', 'end', 'frequency', 'loan', 'option',
            'invoice_number')}
        cls.error_messages.update({
                'premiums_overlap': ('Premiums overlap on contract %s: %s '
                    'end at %s, %s starts at %s'),
                'no_premium_for_policy': 'No premium policy',
                })

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['loan'] = tools.cache_from_query('loan', ('number', ),
            ('number', [r['loan'] for r in rows]))
        cls.cache_obj['contract'] = tools.cache_from_query('contract',
            ('contract_number', ),
            ('contract_number', [r['contract_number'] for r in rows]))

    @classmethod
    def populate(cls, row):
        Contract = Pool().get('contract')

        row = super(MigratorContractPremium, cls).populate(row)
        cls.resolve_key(row, 'contract_number',
            'contract', dest_key='contract')
        cls.resolve_key(row, 'loan', 'loan')
        contract = Contract(row['contract'])
        row['account'] = contract.covered_element_options[0].\
            coverage.account_for_billing
        row['_option'] = contract.covered_element_options[0]
        row['option'] = row['_option'].id
        return row

    @classmethod
    def migrate_premiums(cls, contract_number, rows):
        Premium = Pool().get('contract.premium')

        def pairwise(iterable):
            """s -> (s0,s1), (s1,s2), (s2, s3), ..."""
            a, b = tee(iterable)
            next(b, None)
            return izip(a, b)

        def strip_fields(row):
            return {k: row[k]
                for k in row if k in set(Premium._fields) - {'id', }}

        for row in rows:
            try:
                row = cls.populate(row)
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
        if not rows:
            # si souscription , normal
            # sinon raise error
            cls.raise_error('no_premium_for_policy')
            return

        to_create = [strip_fields(rows[0])]
        for (p1, p2) in pairwise(rows):
            if p1['end'] >= p2['start']:
                cls.raise_error(p1, 'premiums_overlap', (
                    p1['contract_number'], p1['invoice_number'],
                    p1['end'], p2['invoice_number'], p2['start']))
            if (coog_date.number_of_days_between(p2['start'],
                    to_create[-1]['end']) == 0 and
                    p1['amount'] == p2['amount']):
                to_create[-1]['end'] = p2['end']
            else:
                to_create.append(strip_fields(p2))
        to_create[-1]['end'] = None
        return to_create

    @classmethod
    def migrate_rows(cls, rows_all, ids):
        pool = Pool()
        Premium = pool.get('contract.premium')
        Contract = pool.get('contract')

        to_create = []
        delete_contract_numbers = []
        for contract_number, _rows in groupby(rows_all, lambda row: row[
                'contract_number']):
            rows = list(_rows)
            try:
                to_create.extend(cls.migrate_premiums(contract_number, rows))
            except migrator.MigrateError as e:
                cls.logger.error(e)
                delete_contract_numbers.append(contract_number)
                continue

        if to_create:
            to_create = Premium.create(to_create)
        Contract.delete(Contract.search(
            ['contract_number', 'in', delete_contract_numbers]))
        res = {x: None for x in ids if x.split('-')[0] not in
            delete_contract_numbers}
        cls.logger.debug('mig contract premium return %s' % res)
        return res


class MigratorContract(migrator.Migrator):
    """Migrator Contract."""

    __name__ = 'migrator.contract'

    @classmethod
    def __setup__(cls):
        super(MigratorContract, cls).__setup__()

        cls._default_config_items.update({
            'skip_extra_migrators': '',
        })
        if not cls.table:
            cls.table = Table('contract')
            cls.func_key = 'contract_id'
            cls.model = 'contract'
            cls.transcoding = {'status': {}, 'frequency': {},
                'n_de_collectivite': {}, 'franchise': {}}
            cls.cache_obj = {'bank_account': {}, 'contract': {}, 'network': {},
                'party': {}, 'product': {}, 'sepa_mandate': {},
                'billing_mode': {}}
            cls.columns = {k: k for k in ('contract_id', 'contract_number',
                    'version', 'product', 'subscriber', 'covered_person',
                    'status', 'sub_status', 'signature_date',
                    'appliable_conditions_date', 'start_date',
                    'manual_end_date', 'start_management_date', 'dist_network',
                    'agent', 'frequency', 'direct_debit', 'direct_debit_day',
                    'payer')}
            cls.error_messages.update({
                    'not_payer_mandate': ('Cannot use sepa mandate with '
                        'party %s different than contract payer %s.'),
                    'missing_billing_info': ('Account or mandate not '
                        'available. iban: %s, sepa: %s'),
                    'unauthorized_billing_mode': ('Billing mode (%s, %s) not '
                        'present on product %s.'),
                    'bad_substatus': 'Incompatible status/sub-status: %s/%s',
                    'bad_contract_data': '%s',
                    'delete_failed': '%s',
                    'calculate_fail': 'calculate failed: %s %s',
                    })

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['product'] = tools.cache_from_query('offered_product',
            ('code', ))
        ibans = [r['iban'] for r in rows if r['iban']]
        if ibans:
            cls.cache_obj['bank_account'] = tools.cache_from_search(
                'bank.account', 'number', ('number', 'in', ibans))
        sepa_mandates = [r['sepa_mandate'] for r in rows if r['sepa_mandate']]
        if sepa_mandates:
            cls.cache_obj['sepa_mandate'] = tools.cache_from_query(
                'account_payment_sepa_mandate', ('identification', ),
                ('identification', sepa_mandates))
        cls.cache_obj['party'] = tools.cache_from_query(
            'party_party', ('code', ),
            ('code', list(chain.from_iterable(
                [(r['subscriber'], r['covered_person'], r['payer'])
                for r in rows]))))
        cls.cache_obj['network'] = tools.cache_from_query(
            'distribution_network', ('code', ))
        agents = Pool().get('commission.agent').search([])
        cls.cache_obj['agent'] = {x.party.commercial_name: x for x in agents}
        cls.cache_obj['contract'] = tools.cache_from_query(
            'contract', ('contract_number', ),
            ('contract_number', [r['contract_number'] for r in rows]))
        if not cls.cache_obj.get('billing_mode', None):
            cls.cache_obj['billing_mode'] = tools.cache_from_query(
                'offered_product-offered_billing_mode',
                ('product', 'billing_mode'), target='billing_mode')

    @classmethod
    def extra_migrator_names(cls):
        migrators = super(MigratorContract, cls).extra_migrator_names()
        return migrators + [
            'migrator.contract.option',
            'migrator.contract.event',
            'migrator.contract.premium',
        ]

    @classmethod
    def sanitize(cls, row):
        row = super(MigratorContract, cls).sanitize(row)
        row['direct_debit'] = row['direct_debit'] or False
        return row

    @classmethod
    def populate(cls, row):
        pool = Pool()
        ContractSubStatus = pool.get('contract.sub_status')

        cls.resolve_key(row, 'product', 'product')
        cls.resolve_key(row, 'subscriber', 'party')
        cls.resolve_key(row, 'payer', 'party')
        cls.resolve_key(row, 'dist_network', 'network')
        row['agency'] = row['dist_network']
        cls.resolve_key(row, 'agent', 'agent')
        cls.resolve_key(row, 'covered_person', 'party')
        cls.resolve_key(row, 'iban', 'bank_account')
        cls.resolve_key(row, 'sepa_mandate', 'sepa_mandate')

        if row['sub_status']:
            row['sub_status'] = ContractSubStatus.search(
                [('code', '=', row['sub_status'])])[0]
        else:
            row['sub_status'] = None
        row['billing_informations'] = [cls.create_billing_information(row)]
        row['covered_elements'] = [cls.create_covered_element(row)]
        row['quote_number'] = row['contract_number']
        return super(MigratorContract, cls).populate(row)

    @classmethod
    def calculate_contracts(cls, contracts, migrate_premiums=True):
        """Calculate contract. Calculate just activation dates when premiums
           are migrated.
        """
        pool = Pool()
        Contract = pool.get('contract')
        for c in [c for c in contracts.values()
                if c.status != 'terminated']:
            try:
                if migrate_premiums:
                    cls.logger.debug('Calculate contract activation dates')
                    Contract.calculate_activation_dates([c])
                else:
                    cls.logger.debug('Calculate contracts')
                    Contract.calculate([c])
                    Contract.write([c], {'calculated': True})
                c.save()
            except Exception as e:
                cls.logger.error(cls.error_message('calculate_fail') % (
                    c.contract_number, c.start_date, str(e)))
                continue

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()
        Contract = pool.get('contract')
        contracts = {}
        for row in rows:
            try:
                row = cls.populate(row)
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
            contract = Contract(**row)
            contracts[row[cls.func_key]] = contract
        Contract.save(contracts.values())

        skip_extra_migrators = cls.extra_args.get('skip_extra_migrators',
            cls.get_conf_item('skip_extra_migrators')).split(',')
        extra_migrators = [x for x in cls.extra_migrator_names() if x not in
            skip_extra_migrators]

        if contracts:
            for _migrator in extra_migrators:
                cls.logger.info('migrator ex: %s' % _migrator)
                Migrator = Pool().get(_migrator)
                contracts_done = Migrator.migrate(contracts.keys())
                # Remove contracts deleted by extra migrator
                for k in contracts.keys():
                    if k not in contracts_done:
                        contracts.pop(k, None)
                if not contracts:
                    break
        cls.calculate_contracts(contracts,
            'migrator.contract.premium' in extra_migrators)
        return contracts

    @classmethod
    def create_covered_element(cls, row):
        pool = Pool()
        Version = pool.get('contract.covered_element.version')
        CoveredElement = pool.get('contract.covered_element')
        Product = pool.get('offered.product')

        version = Version(**Version.get_default_version())
        version.extra_data = {}
        version.extra_data['qualite'] = row['qualite_assure']
        covered_element = CoveredElement(
                party=row['covered_person'],
                start_date=row['start_date'],
                item_desc=Product(row['product']).coverages[0].item_desc,
                product=row['product'],
                versions=[version]
                )
        return covered_element

    @classmethod
    def create_billing_information(cls, row):
        pool = Pool()
        BillingMode = pool.get('offered.billing_mode')
        BillingInformation = pool.get('contract.billing_information')
        billing_info = BillingInformation(date=row['version'])
        for billing_mode_id in [v for (k, v)
                in cls.cache_obj['billing_mode'].iteritems()
                if k[0] == row['product']]:
            billing_mode = BillingMode(billing_mode_id)
            if (billing_mode.frequency != row['frequency']) or (
                    billing_mode.direct_debit != row['direct_debit']):
                continue
            billing_info.billing_mode = billing_mode_id
            break
        else:
            cls.raise_error(row, 'unauthorized_billing_mode',
                (row['frequency'], row['direct_debit'], row['product'].code))

        # Payment term is deduced from billing mode
        billing_info.payment_term = \
            billing_info.on_change_with_payment_term()
        if billing_info.billing_mode.direct_debit:
            billing_info.direct_debit_day = row['direct_debit_day']
            if row['iban'] and row['sepa_mandate']:
                billing_info.direct_debit_account = row['iban']
                billing_info.sepa_mandate = row['sepa_mandate']
                if row['payer'] != \
                        billing_info.sepa_mandate.party.id:
                    cls.raise_error(row, 'not_payer_mandate',
                        (billing_info.sepa_mandate.party, row['payer']))
            else:
                cls.raise_error(row, 'missing_billing_info', (row['iban'],
                    row['sepa_mandate']))
            billing_info.payer = row['payer']
        return billing_info


class MigratorContractVersion(MigratorContract):
    """Migrator Contract Version."""

    __name__ = 'migrator.contract.version'

    @classmethod
    def __setup__(cls):
        super(MigratorContractVersion, cls).__setup__()
        cls._default_config_items.update({
                'job_size': 1,
                })
        cls.error_messages.update({
                'no_contract_for_endorsement': ("can't apply %s endorsement "
                    "on missing contract"),
                'respawn': "can't reactivate terminated contract",
                'invalid_dates': "invalid dates",
                })

    @classmethod
    def select(cls, extra_args):
        contract = Table('contrat')
        subselect = contract.select(contract.numero_contrat,
            group_by=Column(contract, 'numero_contrat'),
            having=Count(Column(contract, 'numero_contrat')) > 1)
        select = contract.select(contract.identifiant_contrat,
            where=contract.numero_contrat.in_(subselect))
        select.order_by = (contract.numero_contrat,
            contract.numero_avenant)
        return select, cls.func_key

    @classmethod
    def sanitize(cls, row):
        MigratorContract = Pool().get('migrator.contract')
        return MigratorContract.sanitize(row)

    @classmethod
    def query_data(cls, ids):
        MigratorContract = Pool().get('migrator.contract')
        return MigratorContract.query_data(ids)

    @classmethod
    def select_group_ids(cls, ids):
        res = []
        for _, _ids in groupby(ids,
                lambda contract_id: contract_id.split('-')[0]):
            res.append(list(_ids))
        return res

    @classmethod
    def select_remove_ids(cls, ids, excluded, extra_args=None):
        return ids

    @classmethod
    def extra_migrator_names(cls):
        migrators = super(MigratorContract, cls).extra_migrator_names()
        return migrators + [
            'migrator.contract.event',
            ]

    @classmethod
    def migrate_contract_version(cls, row, delta):
        pool = Pool()
        Contract = pool.get('contract')
        ActivationHistory = pool.get('contract.activation_history')
        cls.logger.debug('Version delta: %s' % delta)
        contract = Contract(cls.cache_obj['contract'][row['contract_number']])
        versioned_fields = {'extra_datas': ('franchise', 'n_de_collectivite'),
            'billing_informations': ('frequency', 'direct_debit',
                'direct_debit_day')}
        overwrite_fields = ('status', 'sub_status', 'signature_date',
            'appliable_conditions_date', 'start_date')
        option_fields = ('sub_status', 'status')
        if contract.status == 'terminated' and (delta.get('status',
                None) == 'active'):
            cls.raise_error(row, 'respawn')
            return

        if delta.get('start_date', contract.start_date) > delta.get(
                'manual_end_date',
                row['manual_end_date'] or contract.end_date):
            cls.raise_error(row, 'invalid_dates')
            return
        if 'status' in delta:
            if row['manual_end_date']:
                delta['manual_end_date'] = row['manual_end_date']
        for key in delta:
            if key in list(chain(*versioned_fields.values())):
                key = [x for x in versioned_fields.keys()
                    if key in versioned_fields[x]][0]
                val = list(getattr(contract, key))
                val = val + row[key]
                setattr(contract, key, val)
            elif key in overwrite_fields:
                setattr(contract, key, row[key])
            if key in option_fields:
                for option in contract.covered_elements[0].options:
                    setattr(option, key, row[key])
        if any([k in option_fields for k in delta]):
            for option in contract.covered_elements[0].options:
                option.set_automatic_end_date()
                option.save()
                contract.covered_elements[0].save()
        if 'manual_end_date' in delta:
            contract.activation_history = [ActivationHistory(
                start_date=contract.start_date,
                end_date=row['manual_end_date'])]
        return contract

    @classmethod
    def migrate_rows(cls, rows_all, ids):
        contracts = {}
        cls.logger.info('migrating %s versions rows' % len(rows_all))
        for contract_number, _rows in groupby(rows_all,
                lambda row: row['contract_number']):
            rows = list(_rows)
            last_row = rows[0]  # original contract row
            if last_row['contract_number'] not in cls.cache_obj['contract']:
                cls.logger.error(cls.error_message(
                    'no_contract_for_endorsement') % (
                    last_row['contract_number'],
                    len(rows[1:])))
                continue
            for (idx, row) in enumerate(rows):
                if idx == 0:
                    cls.logger.info('skipping original row')
                    contract = None
                    continue
                delta = tools.diff_rows(last_row, row)
                cls.logger.info('%s version done: %s' % (
                        row['contract_number'], delta))
                try:
                    row = cls.populate(row)
                    contract = cls.migrate_contract_version(row, delta)
                    contract.save()
                    contracts[row['contract_number']] = contract
                except migrator.MigrateError as e:
                    cls.logger.error(e)
                    break
                last_row = row
            else:
                if contract:
                    cls.logger.debug('Calculate contract: %s' %
                        contract.calculated)
                    if contract.calculated:
                        contract.calculate()
                        contract.save()

        if contracts:
            for _migrator in cls.extra_migrator_names():
                Migrator = Pool().get(_migrator)
                Migrator.migrate(contracts.keys())
        cls.logger.info('%s contracts keys' % len(contracts.keys()))
        return contracts


class MigratorContractOption(migrator.Migrator):
    """Migrator contract option"""

    __name__ = 'migrator.contract.option'

    @classmethod
    def __setup__(cls):
        super(MigratorContractOption, cls).__setup__()
        cls.table = Table('contract_option')
        cls.func_key = 'contract_id'
        cls.columns = {k: k for k in ('contract_id', 'contract_number',
            'loan_number', 'option', 'share', 'beneficiary', 'accepting',
            'start_date')}
        cls.error_messages.update({
                'no_option': "no option for contract",
                })

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['loan'] = tools.cache_from_search('loan', 'number',
            ('number', 'in', [r['loan_number'] for r in rows]))
        cls.cache_obj['coverage'] = tools.cache_from_search(
            'offered.option.description', 'code')
        cls.cache_obj['contract'] = tools.cache_from_search('contract',
            'contract_number', ('contract_number', 'in', [r['contract_number']
                for r in rows]))
        if cls.columns['beneficiary']:
            cls.cache_obj['party'] = tools.cache_from_search('party.party',
                'code', ('code', 'in', [r['beneficiary'] for r in rows]))

    @classmethod
    def populate(cls, row):
        pool = Pool()
        LoanShare = pool.get('loan.share')

        row = super(MigratorContractOption, cls).populate(row)
        cls.resolve_key(row, 'loan_number', 'loan', 'loan')
        cls.resolve_key(row, 'contract_number', 'contract', 'contract')
        cls.resolve_key(row, 'option', 'coverage', 'coverage')
        row['loan_shares'] = [LoanShare(start_date=row['start_date'],
            loan=row['loan'], share=row['share'])]
        if cls.columns['beneficiary']:
            Beneficiary = pool.get('contract.option.beneficiary')
            cls.resolve_key(row, 'beneficiary', 'party')
            row['beneficiaries'] = [Beneficiary(accepting=row['accepting'],
                party=row['beneficiary'])]
        return row

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()

        Option = pool.get('contract.option')
        Contract = pool.get('contract')
        ContractLoan = pool.get('contract-loan')
        CoveredElement = pool.get('contract.covered_element')
        to_create = {}
        contracts_in_error = []
        for contract_number, _rows in groupby(rows,
                lambda row: row['contract_number']):
            _rows = list(_rows)
            try:
                rows = [cls.populate(r) for r in _rows]
            except migrator.MigrateError as e:
                cls.logger.error(e)
                contracts_in_error.append(contract_number)
                continue
            contract = rows[0]['contract']
            contract.ordered_loans = [ContractLoan(
                    loan=rows[0]['loan'])]
            options = list(contract.covered_elements[0].options)

            for row in rows:
                try:
                    option = [opt for opt in options
                        if opt.coverage.code == row['option']][0]
                    option.loan_shares = list(option.loan_shares) + \
                        row['loan_shares']
                except IndexError:
                    options.append(Option(coverage=row['coverage'],
                            start_date=row['start_date'],
                            loan_shares=row['loan_shares'],
                            beneficiaries=row.get('beneficiaries', None)))

            contract.covered_elements[0].options = options
            to_create[row['contract_id']] = contract

        CoveredElement.save([c.covered_elements[0]
            for c in to_create.values()])
        Contract.save(to_create.values())

        for c in to_create.values():
            for covered_elem in c.covered_elements:
                for option in covered_elem.options:
                    option.set_automatic_end_date()

        # Delete contracts with no options
        delete_numbers = [x['contract_number']
            for x in [cls.sanitize({'contract_id': k})
                for k in set(ids).difference(to_create.keys())]
            ]
        for number in set(delete_numbers) - set(contracts_in_error):
            cls.logger.error(cls.error_message('no_option') % (number, ))
        Contract.delete(Contract.search(
            ['contract_number', 'in', delete_numbers]))

        return to_create


class MigratorContractPremiumWaiver(migrator.Migrator):
    """Migrator contract premium waiver"""

    __name__ = 'migrator.contract.premium_waiver'

    @classmethod
    def __setup__(cls):
        super(MigratorContractPremiumWaiver, cls).__setup__()
        cls.table = Table('contract_premium_waiver')
        cls.model = 'contract.waiver_premium'
        cls.func_key = 'contract'
        cls.columns = {k: k for k in ('contract', 'start_date',
                'end_date', 'covered_person', 'option')}

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['contract'] = tools.cache_from_search('contract',
            'contract_number', ('contract_number', 'in', [r['contract']
                for r in rows]))
        cls.cache_obj['party'] = tools.cache_from_search('party.party', 'code',
            ('code', 'in', [r['covered_person'] for r in rows]))

    @classmethod
    def populate(cls, row):
        row = super(MigratorContractPremiumWaiver, cls).populate(row)
        cls.resolve_key(row, 'contract', 'contract')
        return row

    @classmethod
    def migrate_rows(cls, rows, ids):
        pool = Pool()
        Model = pool.get(cls.model)
        WaiverOption = Pool().get('contract.waiver_premium-contract.option')

        to_create = {}
        to_create = defaultdict(list)
        for (idx, row) in enumerate(rows[:]):
            try:
                row = cls.populate(row)
                rows[idx] = row
            except migrator.MigrateError as e:
                cls.logger.error(e)
                rows[idx] = None
                continue
            to_create[row[cls.func_key]].append({k: row[k]
                for k in row if k in set(Model._fields) - {'id', }})
        if to_create:
            waivers = Model.create(list(chain(*to_create.values())))

            waiver_options = []
            for waiver in waivers:
                waiver_options.append({'waiver': waiver.id,
                    'option': waiver.contract.covered_element_options[0].id, })
            WaiverOption.create(waiver_options)

        return ids


class MigratorContractEvent(migrator.Migrator):
    """Migrator contract event."""

    __name__ = 'migrator.contract.event'

    @classmethod
    def __setup__(cls):
        super(MigratorContractEvent, cls).__setup__()
        cls.table = Table('contract_event')
        cls.func_key = 'contract_id'
        cls.columns = {k: k for k in ('contract_id', 'version', 'date', 'code',
                'motive')}

    @classmethod
    def init_cache(cls, rows):
        cls.cache_obj['contract'] = tools.cache_from_search('contract',
            'contract_number', ('contract_number', 'in', [r['contract_number']
                for r in rows]))

    @classmethod
    def populate(cls, row):
        row = super(MigratorContractEvent, cls).populate(row)
        cls.resolve_key(row, 'contract_number', 'contract', 'contract')
        return row

    @classmethod
    def migrate_rows(cls, rows, ids):
        Event = Pool().get('event')
        pool = Pool()
        EventLog = pool.get('event.log')
        for row in rows:
            try:
                row = cls.populate(row)
            except migrator.MigrateError as e:
                cls.logger.error(e)
                continue
            cls.logger.info('Notify event for %s %s' % (row['contract_number'],
                row['contract']))
            event_type_id = Event.get_event_type_data_from_code(
                row['code'])['id']
            EventLog.create_event_logs([row['contract']], event_type_id,
                u'n°%s %s' % (row['version'], row.get('motive', '')),
                date=datetime.datetime(row['date'].year, row['date'].month,
                    row['date'].day))
        return {id: None for id in ids}
