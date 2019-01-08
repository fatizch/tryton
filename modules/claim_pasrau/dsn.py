# encoding: utf8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from itertools import groupby
from decimal import Decimal
from sql import Null, Literal
from sql.operators import Not

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import utils
from trytond.modules.dsn_standard import dsn
from trytond.config import config


class ZeroLine(object):

    def __init__(self, party):
        self.party = party


class NEORAUTemplate(dsn.NEODeSTemplate):

    custom_mapping = {

        # BLOC ENTREPRISE (SIREN LEVEL)

        'S21.G00.06.001': 'siren',
        # 'S21.G00.06.002': '',  # NIC du siège
        'S21.G00.06.003': 'conf_code_apen',
        'S21.G00.06.004': 'main_address.one_line_street',
        'S21.G00.06.005': 'main_address.zip',
        'S21.G00.06.006': 'main_address.city',
        # 'S21.G00.06.007': '',  # Complément de la localisation de la constr.
        # 'S21.G00.06.008': '',  # Service de distribution, complément de loc.
        'S21.G00.06.010': 'main_address_country_code',
        # 'S21.G00.06.011': '',  # Code de distribution à l'étranger

        # BLOC ETABLISSEMENT (SIRET LEVEL)

        'S21.G00.11.001': 'conf_nic_etablissement',
        'S21.G00.11.002': 'conf_apet_etablissement',
        'S21.G00.11.003': 'main_address.one_line_street',
        'S21.G00.11.004': 'main_address.zip',
        'S21.G00.11.005': 'main_address.city',
        # 'S21.G00.11.006': '',  # Complément de la localisation de la constr.
        # 'S21.G00.11.007': '',  # Service de distribution, complément de loc.
        'S21.G00.11.015': 'main_address_country_code',
        # 'S21.G00.11.016': '',  # Code de distribution à l'étranger

        # BLOC  VERSEMENT ORGANISME

        'S21.G00.20.001': 'dgfip',
        'S21.G00.20.003': 'pasrau_bic',
        'S21.G00.20.004': 'pasrau_iban',
        'S21.G00.20.005': 'pasrau_total_amount',
        'S21.G00.20.006': 'pasrau_slip_start_date',
        'S21.G00.20.007': 'invoice_date',
        'S21.G00.20.010': 'pasrau_payment_mode',
        # 'S21.G00.20.012': '',  # SIRET Payeur

        # BLOC INDIVIDU

        'S21.G00.30.001': 'ssn_no_key',
        'S21.G00.30.002': 'birth_name_or_name',
        'S21.G00.30.003': 'usage_name',
        'S21.G00.30.004': 'first_name',
        'S21.G00.30.005': 'gender',
        'S21.G00.30.006': 'birth_date',
        'S21.G00.30.007': 'birth_place',
        'S21.G00.30.008': 'main_address.one_line_street',
        'S21.G00.30.009': 'main_address.zip',
        'S21.G00.30.010': 'main_address.city',
        'S21.G00.30.011': 'main_address_country_code',
        # 'S21.G00.30.012': '',  # Code de distribution à l'étranger
        'S21.G00.30.014': 'birth_department',
        # 'S21.G00.30.015': '',  # Code pays de naissance
        # 'S21.G00.30.016': '',  # Complément de la localisation
        # 'S21.G00.30.017': '',  # Service de distribution, complément de loc.
        'S21.G00.30.019': 'code',  # Matricule de l'individu dans l'entreprise
        # 'S21.G00.30.020': '',  # Numéro technique temporaire

        'S21.G00.31.001': 'modification_date',  # Date de la modification
        'S21.G00.31.008': 'ssn',  # Ancien NIR
        'S21.G00.31.009': 'name',  # Ancien Nom de famille
        'S21.G00.31.010': 'first_name',  # Anciens Prénoms
        'S21.G00.31.011': 'birth_date',  # Ancienne Date de naissance

        # BLOC VERSEMENT INDIVIDU

        'S21.G00.50.001': 'pasrau_reconciliation_date',
        'S21.G00.50.002': 'pasrau_base',
        # 'S21.G00.50.003': '',  # Numéro de versement (C)
        # 'S21.G00.50.005': '',  # Rémunération nette fiscale potentielle (C)
        'S21.G00.50.006': 'pasrau_rate',
        'S21.G00.50.007': 'pasrau_rate_kind',
        'S21.G00.50.008': 'pasrau_rate_id',
        'S21.G00.50.009': 'pasrau_debit_amount',
        # 'S21.G00.50.010': '',  # Date de fin de la relation
        # entre la personne et l’organisme C


        # BLOC RÉGULARISATION DU PRÉLÈVEMENT À LA SOURCE

        'S21.G00.56.001': 'pasrau_error_month',
        'S21.G00.56.002': 'pasrau_error_type',
        'S21.G00.56.003': 'pasrau_regularization_base',
        # Rémunération nette fiscale déclarée le mois de l’erreur C
        # 'S21.G00.56.004': '',
        #   Régularisation du taux de prélèvement à la source C
        # 'S21.G00.56.005': '',
        'S21.G00.56.006': 'pasrau_rate',
        'S21.G00.56.007': 'pasrau_regularization_debit_amount'
    }

    translations = {
        'gender': {'male': '01', 'female': '02'}
        }

    def __init__(self, origin, testing=False, void=False, replace=False):
        super(NEORAUTemplate, self).__init__(origin, testing, void)
        if not void:
            self.load_data()
        if not replace:
            done_messages = self.origin._get_month_dsn_messages(['done'])
            if done_messages:
                self.replace = True
                if not config.getboolean('env', 'testing'):
                    self.origin.check_date_dsn_message_generation()

    def load_specifications(self):
        self.spec = NEORAU()

    def load_data(self):
        pool = Pool()
        MoveLine = pool.get('account.move.line')
        Tax = pool.get('account.tax')
        DSNMessage = pool.get('dsn.message')
        account_ids = [x.invoice_account.id
            for x in Tax.search([('type', '=', 'pasrau_rate')])]

        associated_lines = MoveLine.search([
                ('principal_invoice_line.invoice', '=', self.origin.id),
                ('account', 'in', account_ids),
                ])

        def keyfunc(line):
            return self.get_invoice_from_move_line(line).party

        sorted_lines = sorted(associated_lines, key=keyfunc)

        data = {'individuals': {}}
        for party, grouped_lines in groupby(sorted_lines, key=keyfunc):
            def key(x):
                return self.get_invoice_from_move_line(x)

            lines = sorted(list(grouped_lines), key=key)
            add_to_zero_individual = True

            to_output = []
            for invoice, invoice_group_lines in groupby(lines, key=key):
                invoice_group_lines = list(invoice_group_lines)

                sum_ = sum([line.credit - line.debit for line in
                        invoice_group_lines])
                by_date = sorted(invoice_group_lines,
                    key=lambda x: x.create_date)

                last = by_date.pop()
                if sum_ != Decimal('0.0'):
                    if len(by_date) >= 1:
                        # Check that the sum of the outstanding line are zero
                        # Normally these lines cancel each other
                        rest_sum = sum([line.credit - line.debit
                                for line in by_date])
                        assert rest_sum in (0, Decimal(0.0)), rest_sum
                    add_to_zero_individual = False
                    to_output.append(last)

            if add_to_zero_individual:
                to_output.append(ZeroLine(party))

            data['individuals'][party] = {'lines': to_output}

        individuals_at_zero = self.fetch_individuals_at_zero(associated_lines,
            data['individuals'])
        assert not any(x in data['individuals'] for x in individuals_at_zero)

        data['individuals'].update({x: {'lines': [ZeroLine(x)]}
            for x in individuals_at_zero})

        # manage person modification
        from_date = DSNMessage.last_dsn_message_create_date()
        for party in list(data['individuals'].keys()):
            modifications = []
            for modification in party.pasrau_modified_fields(from_date,
                    self.origin.create_date):
                modifications.append(
                    utils.DictAsObject(modification, fail_on_miss=False))
            data['individuals'][party]['modifications'] = modifications

        self.data = data
        if not self.data['individuals']:
            self.void = True

    def fetch_individuals_at_zero(self, associated_lines, slip_parties):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        Party = pool.get('party.party')
        party = Party.__table__()
        account_tax = pool.get('account.tax').__table__()
        claim = pool.get('claim').__table__()
        indemnification = pool.get('claim.indemnification').__table__()
        loss = pool.get('claim.loss').__table__()
        service = pool.get('claim.service').__table__()
        product = pool.get('product.product').__table__()
        template = pool.get('product.template').__table__()
        category = pool.get('product.category').__table__()
        supplier_tax = pool.get('product.category-supplier-account.tax'
            ).__table__()

        query_table = indemnification.join(party, condition=(
                (indemnification.beneficiary == party.id)
                & (indemnification.status == 'paid'))
            ).join(service, condition=(
                indemnification.service == service.id)
            ).join(loss, condition=(
                service.loss == loss.id)
            ).join(claim, condition=(
                loss.claim == claim.id)
            ).join(product, condition=(
                indemnification.product == product.id)
            ).join(template, condition=(
                product.template == template.id)
            ).join(category, condition=(
                template.account_category == category.id)
            ).join(supplier_tax, condition=(
                category.id == supplier_tax.category)
            ).join(account_tax, condition=(
                supplier_tax.tax == account_tax.id)
            )

        where_clause = ((claim.status.in_(['open', 'reopened']))
            & (account_tax.type == 'pasrau_rate')
            & (party.is_person == Literal(True))
            & (service.annuity_frequency != Null))

        slip_parties_ids = [x.id for x in slip_parties]

        if slip_parties_ids:
            where_clause &= (Not(party.id.in_(slip_parties_ids)))

        cursor.execute(*query_table.select(party.id,
            where=where_clause))
        party_ids = [p for p, in cursor.fetchall()]
        return Party.browse(party_ids)

    def get_instances(self, block_id, parent):
        if block_id == 'S21.G00.06':  # declaring siren entity
            return [self.origin.company.party]
        elif block_id == 'S21.G00.11':  # declaring siret entity
            return [self.origin.company.party]
        elif block_id == 'S21.G00.20':  # total amount + banking info
            return [self.origin]
        elif block_id == 'S21.G00.30':
            return list(self.data['individuals'].keys())
        elif block_id == 'S21.G00.31':
            return self.data['individuals'][parent]['modifications']
        elif block_id == 'S21.G00.50':
            return self.data['individuals'][parent]['lines']
        elif block_id == 'S21.G00.56':
            # a regularization block only for negative lines
            if (parent and not isinstance(parent, ZeroLine) and
                    (parent.credit - parent.debit) < Decimal('0.0')):
                return [parent]
            else:
                return []
        else:
            return super(NEORAUTemplate, self).get_instances(block_id, parent)

    def get_invoice_from_move_line(self, line):
        if line.move.invoice:
            return line.move.invoice
        if line.move.origin.__name__ == 'account.invoice':
            return line.move.origin
        assert False, "Can't find invoice for line %s on move %s" % (
            line.rec_name, line.move.rec_name)

    @property
    def declaration_nature(self):
        return '11'

    @property
    def declaration_rank(self):
        Message = Pool().get('dsn.message')
        messages = Message.search([
                ('origin', '=', str(self.origin)),
                ('state', '=', 'done')],
            order=[('create_date', 'ASC')])
        return str(len(messages) + 1)

    @property
    def declaration_month(self):
        return str(self.origin.invoice_date.strftime('01%m%Y'))

    def custom_dgfip(self, slip):
        return 'DGFiP'

    def custom_pasrau_bic(self, slip):
        return slip.company.party.bank_accounts[0].bank.bic

    def custom_pasrau_iban(self, slip):
        return slip.company.party.bank_accounts[0].numbers[0].number_compact

    def custom_birth_name_or_name(self, party):
        return party.birth_name if party.birth_name else party.name

    def custom_usage_name(self, party):
        # fill S21.G00.30.003 only if birth name is empty
        return party.name if party.birth_name else None

    def custom_pasrau_total_amount(self, slip):
        return slip.total_amount if slip.total_amount else Decimal('0')

    def custom_pasrau_slip_start_date(self, slip):
        return datetime.date(slip.invoice_date.year, slip.invoice_date.month,
            1)

    def custom_pasrau_payment_mode(self, slip):
        return '05'  # This means sepa direct debit

    def custom_gender(self, party):
        return self.translations['gender'][party.gender]

    def custom_birth_place(self, party):
        return 'SLN'

    def custom_birth_department(self, party):
        return '00'

    def get_pasrau_tax_line(self, line):
        invoice = self.get_invoice_from_move_line(line)
        for tax_line in invoice.taxes:
            if (tax_line.tax.invoice_account == line.account and
                    abs(tax_line.amount) == abs(line.credit - line.debit)):
                return tax_line

    def custom_pasrau_reconciliation_date(self, line):
        if isinstance(line, ZeroLine):
            return self.origin.invoice_date
        return self.get_invoice_from_move_line(line).reconciliation_date

    def custom_pasrau_base(self, line):
        # We declare a zero block and a regularization for negative lines
        if (isinstance(line, ZeroLine) or
                (line.credit - line.debit) < Decimal('0.0')):
            return Decimal('0.0')
        return self.get_pasrau_tax_line(line).base

    def custom_pasrau_debit_amount(self, line):
        # We declare a zero block and a regularization for negative lines
        if (isinstance(line, ZeroLine) or
                (line.credit - line.debit) < Decimal('0.0')):
            return Decimal('0.0')
        return self.get_pasrau_tax_line(line).amount * -1

    def custom_pasrau_rate(self, line):
        if isinstance(line, ZeroLine):
            return Decimal('0.0')
        return line.pasrau_rates_info[0].pasrau_rate * Decimal('100.0')

    def custom_pasrau_rate_kind(self, line):
        DefaultPasrauRate = Pool().get('claim.pasrau.default.rate')
        if isinstance(line, ZeroLine):
            region = DefaultPasrauRate.get_region(line.party.main_address.zip)
        else:
            region = line.pasrau_rates_info[0].pasrau_rate_region
        if not region:
            return '01'
        return {
            'metropolitan': '17',
            'grm': '27',
            'gm': '37',
            }.get(region)

    def custom_pasrau_rate_id(self, line):
        return '-1'  # TODO : should be stored on perso rate from DGFIP crm

    def custom_pasrau_error_month(self, line):
        # todo : what is the date of the error ?
        return str(self.origin.invoice_date.strftime('%m%Y'))

    def custom_pasrau_error_type(self, line):
        return '03'

    def custom_pasrau_regularization_base(self, line):
        return self.get_pasrau_tax_line(line).base

    def custom_pasrau_regularization_debit_amount(self, line):
        return self.get_pasrau_tax_line(line).amount


class NEORAU(dsn.NEODES):

    def get_resource_file_name(self, kind):
        # The files below are the "Fields", "Data Types", "Blocks" tab from
        # https://www.net-entreprises.fr/wp-content/uploads/2018/06/
        # PASRAU-tableau-categories-datatypes-2017.6.xlsx
        # encoding is utf8
        # I renamed the "Nature" column to "Name" in the datatypes file
        # to match dsn Spec
        return 'PASRAU-tableau-categories-datatypes-2017.6_%s.csv' % kind
