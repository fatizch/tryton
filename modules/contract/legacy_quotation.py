import copy
from uuid import uuid4
from decimal import Decimal
from collections import namedtuple, defaultdict

from trytond.pool import Pool
from trytond.modules.api import APIError

# TODO : create fake non person if subscriber_kind == company
# TODO: get insured capital at each invoice start
# TODO: handle billing mode entered in quotation


def nanoid():
    return str(uuid4())


class LegacyColumn(namedtuple('LegacyColumn', 'id label type party_ref')):

    def to_json(self):
        dict_ = dict(self._asdict())  # _asdict returns an orderdict
        dict_.pop('party_ref')
        dict_['id'] = self.full_id
        return dict_

    @property
    def full_id(self):
        return self.label + self.id


class LegacyQuotation(object):

    def __init__(self, legacy_input):
        pool = Pool()
        APIContract = pool.get('api.contract')
        self.legacy_input = legacy_input
        self.simulate_input = self.quotation_to_simulate_input()
        api_context = {
            'dist_network': legacy_input['broker']}
        res = APIContract.simulate(self.simulate_input, api_context)
        self.sim_results = res
        if isinstance(self.sim_results, APIError):
            return
        self.first_invoice_data = self.get_premium_contract_data(
            self.sim_results, 'first_invoice')
        self.first_year_data = self.get_premium_contract_data(
            self.sim_results, 'first_year')
        self.average_data = self.get_average_data(self.sim_results)
        if self.is_loan:
            self.per_loan_data = self.build_per_loan_data()
        self.build_premium_summary()

    def quotation_to_simulate_input(self):
        pool = Pool()
        legacy_input = self.legacy_input
        sim_loans = []
        sim_parties = []
        sim_party_coverages = []
        self.is_loan = bool(legacy_input.get('loan'))
        self.loan_idx_holding_fee = None

        if self.is_loan:
            for i, legacy_loan in enumerate(legacy_input['loan']):
                sim_loan = dict(legacy_loan)
                for k in ('rate', 'amount'):
                    if k in sim_loan:
                        sim_loan[k] = str(sim_loan[k])
                if sim_loan.get('kind') == 'interest_free':
                    sim_loan.pop('deferral', None)
                if sim_loan.get('kind') == 'graduated':
                    rate = sim_loan.pop('rate', None)
                    sim_loan.pop('duration', None)
                    sim_loan.pop('duration_unit', None)
                    sim_loan.pop('deferral_duration', None)
                    sim_loan.pop('payment_frequency', None)
                    for inc in sim_loan['increments']:
                        inc['payment_amount'] = str(
                            Decimal(inc['payment_amount']))
                        if rate and not inc.get('rate'):
                            inc['rate'] = rate
                sim_loan['ref'] = str(i)
                sim_loan.pop('lender')
                release_date = sim_loan.pop('release_date', None)
                sim_loan['funds_release_date'] = release_date
                sim_loans.append(sim_loan)

        for i, legacy_covered in enumerate(legacy_input['covered']):
            sim_party = dict(legacy_covered['party'])
            sim_party['ref'] = str(i)
            sim_parties.append(sim_party)
            sim_party_coverage = {
                'party': {'ref': sim_party['ref']},
                'item_descriptor': {'code': legacy_covered['type']},
                'extra_data': legacy_covered['extra'],
                }
            covered_package = legacy_covered.get('package')
            if legacy_covered.get('package'):
                sim_party_coverage['package'] = {'code': covered_package}
            # ? only subscribe by package or not ?
            sim_party_coverage['coverages'] = []
            for code, selection in legacy_covered['coverage'].items():
                if selection['selected']:
                    sim_option = {'coverage': {'code': code}}
                    if self.is_loan:
                        sim_shares = [
                            {
                                'loan': {'ref': sim_loan['ref']},
                                'share': str(Decimal(
                                        legacy_covered['share']) / Decimal(100))
                            } for sim_loan in sim_loans]
                        sim_option['loan_shares'] = sim_shares
                    sim_party_coverage['coverages'].append(sim_option)
                    # should we handle beneficiary clauses ?
            sim_party_coverages.append(sim_party_coverage)

        Product = pool.get('offered.product')
        product = Product(legacy_input['product'])
        self.product = product
        yearly, = [x for x in product.billing_rules[0].billing_modes
            if x.frequency == 'yearly']
        billing_ref = {'billing_mode': {'id': yearly.id}}

        if self.is_loan:  # This should be: product.single_covered
            contracts = []
            for i, sim_party_coverage in enumerate(sim_party_coverages):
                contract = {
                        'ref': str(i),
                        'subscriber': {'ref': str(i)},
                        'product': {'id':
                            legacy_input['product']},
                        'commercial_product': {'id': legacy_input[
                            'commercial_product']['id']},
                        'covereds': [sim_party_coverage],
                        'extra_data': legacy_input['extra'],
                        'billing': dict(billing_ref),
                        }
                contracts.append(contract)
        else:
            contracts = [{
                    'ref': '0',
                    'subscriber': {'ref': '0'},  # arbitrary
                    'product': {'id':
                        legacy_input['product']},
                    'commercial_product': {'id': legacy_input[
                        'commercial_product']['id']},
                    'covereds': sim_party_coverages,
                    'extra_data': legacy_input['extra'],
                    'billing': dict(billing_ref),
                    }]
        summary_kind = 'contract_first_term'
        sim_input = {
            'options': {
                'premium_summary_kind': summary_kind,
            },
            'parties': sim_parties,
            'contracts': contracts,
        }
        if self.is_loan:
            sim_input['loans'] = sim_loans
            self.fee_holding_loan_ref = self.get_fee_holding_loan_ref(
                sim_loans)

        return sim_input

    def get_fee_holding_loan_ref(self, sim_loans):
        apr_rule = self.product.average_loan_premium_rule
        if not apr_rule or not apr_rule.use_default_rule or \
                apr_rule.default_fee_action == 'prorata':
            raise NotImplementedError
        fee_action = apr_rule.default_fee_action

        if fee_action == 'do_not_use':
            return None
        elif len(sim_loans) == 1:
            return sim_loans[0]['ref']
        elif fee_action == 'longest':
            return sorted(sim_loans,
                key=lambda x: x['duration'])[-1]['ref']
        elif fee_action == 'longest':
            return sorted(sim_loans,
                key=lambda x: x['amount'])[-1]['ref']

    def get_prices_board(self):
        if isinstance(self.sim_results, APIError):
            return self.sim_results.format_error()
        board = self.build_prices_board()
        return board

    def build_prices_board(self):
        first_column_label = '' if self.is_loan else 'coverages'
        detailsColumn = LegacyColumn(nanoid(), first_column_label, 'string',
            None)
        feesColumn = LegacyColumn(nanoid(), 'fees', 'currency',
            None)  # To be translated portal-side
        totalColumn = LegacyColumn(nanoid(), 'total', 'currency',
            None)

        covered_columns = []

        if self.is_loan:  # This should be: product.single_covered
            covereds = [x['covereds'][0] for x in self.sim_results]
        else:
            covereds = self.sim_results[0]['covereds']

        for covered in covereds:
            ref = covered['party'].get('ref')
            idx = int(ref)
            legacy_party = self.legacy_input['covered'][idx]['party']
            party_name = ' '.join([legacy_party.get(x)
                    for x in ('name', 'first_name') if legacy_party.get(x)])
            covered_columns.append(
                LegacyColumn(nanoid(), party_name, 'currency', ref))
        if self.is_loan:
            all_columns = [detailsColumn] + covered_columns + [feesColumn] + \
                [totalColumn]
        else:
            all_columns = [detailsColumn] + covered_columns + [totalColumn]

        row_maker = self.build_loan_board_rows if self.is_loan \
            else self.build_basic_board_rows
        rows = row_maker(all_columns)

        res = {'columns': [x.to_json() for x in all_columns], 'data': rows,
            'premium_summary': self.premium_summary, 'schedules': [x['schedule']
                for x in self.sim_results]}
        return res

    def build_premium_summary(self):

        by_covered = []

        data_map = {
            'mean': self.average_data,
            'all_contract': self.sim_results,
            'first': self.first_invoice_data,
            'first_year': self.first_year_data,
            }

        for i in range(len(self.legacy_input['covered'])):
            covered_data = {'all_coverages': {}, 'whole_price': {}, 'fees': {}}
            for key, reference_data in data_map.items():
                # TODO: product.single_covered
                premium = reference_data[i].get('premium') if self.is_loan \
                    else reference_data[0]['covereds'][i].get('premium')
                covered_data['all_coverages'][key] = \
                    self.format_premium_tax_included(premium)
                # TODO: product.single_covered
                whole_price = reference_data[i]['premium']['total'] \
                    if self.is_loan else \
                    reference_data[0]['covereds'][i]['premium']['total']
                covered_data['whole_price'][key] = self.format_amount(
                    whole_price)
                covered_data['fees'][key] = [{
                        'code': x['code'],
                        'amount': self.format_amount(x['amount'])}
                    for x in premium['fees']]
            if self.is_loan:
                covered_data['taea'] = self.sim_results[i]['taea']
                for t in covered_data['taea']:
                    t['taea'] = self.format_amount(t['taea'])

            covered_coverages = {}

            # a bit dangerous to relay on order of coverages
            def coverage_loop():
                # TODO: product.single_covered
                if self.is_loan:
                    for j, coverage in enumerate(
                            self.sim_results[i]['covereds'][0]['coverages']):
                        yield j, coverage
                else:
                    for j, coverage in enumerate(
                            self.sim_results[0]['covereds'][i]['coverages']):
                        yield j, coverage

            for j, coverage in coverage_loop():
                code = coverage['coverage']['code']
                coverage_data = {}
                for key, reference_data in data_map.items():
                    # TODO: product.single_covered
                    premium = reference_data[i]['covereds'][0][
                        'coverages'][j].get('premium') if self.is_loan else \
                            reference_data[0]['covereds'][i][
                                'coverages'][j].get('premium')
                    coverage_data[key] = self.format_premium_tax_included(
                        premium)
                covered_coverages[code] = coverage_data

            covered_data['by_coverage'] = covered_coverages
            if self.is_loan:
                covered_data['by_loan'] = \
                    self.get_per_loan_covered_aggregates(self.per_loan_data[i])
            by_covered.append(covered_data)

        premium_summary = {'by_covered': by_covered}
        if self.is_loan:
            premium_summary['fee_holding_loan_ref'] = self.fee_holding_loan_ref
        self.premium_summary = premium_summary

    def format_premium_tax_included(self, premium):
        if premium is None:
            return 0.0
        else:
            premium_tax_included = Decimal(premium['total_premium']
                ) + Decimal(premium['total_tax'])
            return self.format_amount(premium_tax_included)

    def build_loan_board_rows(self, all_columns):
        row_name_col = all_columns[0]
        total_col = all_columns[-1]
        fee_col = all_columns[-2]
        covered_cols = all_columns[1:-2]
        rows = []

        data_map = {
            'premium_sum': self.sim_results,
            'premium_taea': self.sim_results,
            'premium_first': self.first_invoice_data,
            'premium_first_year_sum': self.first_year_data,
            'premium_mean': self.average_data,
            }

        for row_kind in ('premium_sum', 'premium_mean',
                'premium_first_year_sum', 'premium_first',
                'premium_taea'):
            row_desc = 'quotation.offer.' + row_kind
            row = {
                'id': row_desc + nanoid(),
                row_name_col.id: row_desc,
                }

            reference_data = data_map[row_kind]
            if row_kind != 'premium_taea':
                row[total_col.full_id] = self.format_amount(
                    sum([Decimal(x['premium']['total'])
                            for x in reference_data]))
                row[fee_col.full_id] = self.format_amount(
                    sum([Decimal(x['premium']['total_fee'])
                            for x in reference_data]))
            for covered_col in covered_cols:
                party_ref = covered_col.party_ref
                party_idx = int(party_ref)
                if row_kind == 'premium_taea':
                    # how do we display taea in the board
                    # if there are several loans ?
                    taea = reference_data[party_idx]['taea'][0]['taea']
                    row[covered_col.full_id] = {
                        'value': self.format_amount(taea),
                        'format': 'percent'}
                else:
                    party_sim_res = reference_data[party_idx]['covereds'][0]
                    row[covered_col.full_id] = self.format_amount(
                        party_sim_res['premium']['total'])
            rows.append(row)
        return rows

    def format_amount(self, amount_str):
        return float(Decimal(amount_str))

    def build_basic_board_rows(self, all_columns):
        Coverage = Pool().get('offered.option.description')
        row_name_col = all_columns[0]
        total_col = all_columns[-1]
        covered_cols = all_columns[1:-1]
        by_coverage = defaultdict(dict)
        rows = []
        for covered in self.first_invoice_data[0]['covereds']:
            for coverage in covered['coverages']:
                premium = coverage.get('premium')
                by_coverage[coverage['coverage']['code']][
                    covered['party']['ref']] = premium

        name_by_code = {cov.code: cov.name for
            cov in Coverage.search([('code', 'in',
                        list(by_coverage.keys()))])}

        all_total = Decimal(0)
        for code, by_party in by_coverage.items():
            row = {
                'id': nanoid(),
                row_name_col.full_id: name_by_code[code],
                }
            all_party_total = Decimal(0)
            for covered_col in covered_cols:
                party_ref = covered_col.party_ref
                premium_data = by_party.get(party_ref)
                if premium_data:
                    party_total = premium_data['total']
                else:
                    party_total = "0"
                row[covered_col.full_id] = self.format_amount(party_total)
                all_party_total += Decimal(party_total)
            row[total_col.full_id] = self.format_amount(all_party_total)
            all_total += all_party_total
            rows.append(row)

        fees = self.sim_results[0]['premium']['total_fee']
        all_total += Decimal(fees)

        fees_row = {
            'id': nanoid(),
            row_name_col.full_id: 'Fees',
            total_col.full_id: self.format_amount(fees)}

        total_row = {
            'id': nanoid(),
            row_name_col.full_id: 'Total',
            total_col.full_id: self.format_amount(all_total)}

        rows.extend([fees_row, total_row])

        return rows

    def get_premium_contract_data(self, schedules, summary_kind):
        pool = Pool()
        APIContract = pool.get('api.contract')
        contracts = []
        for res in schedules:
            contract_data = copy.deepcopy(res)
            self.reset_schedule_premium_data(contract_data)
            APIContract._aggregate_schedule(None, contract_data, summary_kind)
            contracts.append(contract_data)
        return contracts

    def get_average_data(self, schedules):
        pool = Pool()
        APIContract = pool.get('api.contract')
        contracts = []

        def average_premium(p, nb_invoices):
            for key, value in p.items():
                if key == 'fees':
                    for fee in value:
                        fee['amount'] = str(Decimal(fee['amount']) /
                            Decimal(nb_invoices))
                else:
                    p[key] = str(Decimal(value) / Decimal(nb_invoices))

        for res in schedules:
            contract_data = copy.deepcopy(res)
            self.reset_schedule_premium_data(contract_data)
            APIContract._aggregate_schedule(None, contract_data,
                'contract_first_term')
            nb_invoices = len(contract_data['schedule'])

            for covered in contract_data['covereds']:
                average_premium(covered['premium'], nb_invoices)
                for coverage in covered['coverages']:
                    if coverage.get('premium'):
                        average_premium(coverage['premium'], nb_invoices)

            average_premium(contract_data['premium'], nb_invoices)
            contracts.append(contract_data)
        return contracts

    def get_per_loan_covered_aggregates(self, per_loan_covered_schedules):
        per_loan = []

        for loan_idx, schedule in enumerate(per_loan_covered_schedules):
            data_map = {
                'mean': self.get_average_data([schedule])[0],
                # hum : the calculation is done twice for contract_first_term
                'all_contract': self.get_premium_contract_data([schedule],
                    'contract_first_term')[0],
                'first': self.get_premium_contract_data([schedule],
                    'first_invoice')[0],
                'first_year': self.get_premium_contract_data([schedule],
                    'first_year')[0]
                }
            covered_data = {'all_coverages': {}, 'whole_price': {}}
            for key, reference_data in data_map.items():
                premium = reference_data.get('premium')
                covered_data['all_coverages'][key] = \
                    self.format_premium_tax_included(premium)
                covered_data['whole_price'][key] = \
                    self.format_amount(reference_data['premium']['total'])
                covered_data['taea'] = [schedule['taea'][loan_idx]]
                for t in covered_data['taea']:
                    t['taea'] = self.format_amount(t['taea'])

            # a bit dangerous to relay on order of coverages
            covered_coverages = {}
            for j, coverage in enumerate(
                    schedule['covereds'][0]['coverages']):
                code = coverage['coverage']['code']
                coverage_data = {}
                for key, reference_data in data_map.items():
                    premium = reference_data['covereds'][0][
                        'coverages'][j].get('premium')
                    coverage_data[key] = self.format_premium_tax_included(
                        premium)
                covered_coverages[code] = coverage_data

            covered_data['by_coverage'] = covered_coverages
            per_loan.append(covered_data)

        return per_loan

    def reset_schedule_premium_data(self, contract_data):
        if 'premium' in contract_data:
            del contract_data['premium']
        for covered in contract_data['covereds']:
            if 'premium' in covered:
                del covered['premium']
            for coverage in covered['coverages']:
                if 'premium' in coverage:
                    del coverage['premium']

    def build_per_loan_data(self):
        per_covered_per_loan = []
        for res in self.sim_results:
            contracts = []
            loan_refs = [x['loan']['ref'] for x in res['taea']]
            for ref in loan_refs:
                contract_data = copy.deepcopy(res)
                for invoice in contract_data['schedule']:
                    loan_details = []
                    for detail in invoice['details']:
                        if 'fee' in detail['origin'] and \
                                ref == self.fee_holding_loan_ref:
                            loan_details.append(detail)
                            continue
                        loan = detail.get('loan')
                        if not loan or loan['ref'] != ref:
                            continue
                        loan_details.append(detail)
                    invoice['details'] = loan_details
                contracts.append(contract_data)
            per_covered_per_loan.append(contracts)
        return per_covered_per_loan
