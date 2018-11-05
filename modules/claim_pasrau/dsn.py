# encoding: utf8
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from itertools import groupby
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from sql import Null
from sql.operators import Not

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.dsn_standard import dsn
from trytond.config import config


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
        'S21.G00.06.010': 'main_address.country.code',
        # 'S21.G00.06.011': '',  # Code de distribution à l'étranger

        # BLOC ETABLISSEMENT (SIRET LEVEL)

        'S21.G00.11.001': 'conf_nic_etablissement',
        'S21.G00.11.002': 'conf_apet_etablissement',
        'S21.G00.11.003': 'main_address.one_line_street',
        'S21.G00.11.004': 'main_address.zip',
        'S21.G00.11.005': 'main_address.city',
        # 'S21.G00.11.006': '',  # Complément de la localisation de la constr.
        # 'S21.G00.11.007': '',  # Service de distribution, complément de loc.
        'S21.G00.11.015': 'main_address.country.code',
        # 'S21.G00.11.016': '',  # Code de distribution à l'étranger

        # BLOC  VERSEMENT ORGANISME

        'S21.G00.20.001': 'dgfip',
        'S21.G00.20.003': 'pasrau_bic',
        'S21.G00.20.004': 'pasrau_iban',
        'S21.G00.20.005': 'pasrau_total_amount',
        'S21.G00.20.006': 'invoice_date',
        'S21.G00.20.007': 'pasrau_slip_end_date',
        'S21.G00.20.010': 'pasrau_payment_mode',
        # 'S21.G00.20.012': '',  # SIRET Payeur

        # BLOC INDIVIDU

        'S21.G00.30.001': 'ssn',
        'S21.G00.30.002': 'name',
        # 'S21.G00.30.003': '',  # Nom d'usage
        'S21.G00.30.004': 'first_name',
        'S21.G00.30.005': 'gender',
        'S21.G00.30.006': 'birth_date',
        'S21.G00.30.007': 'birth_place',
        'S21.G00.30.008': 'main_address.one_line_street',
        'S21.G00.30.009': 'main_address.zip',
        'S21.G00.30.010': 'main_address.city',
        'S21.G00.30.011': 'main_address.country.code',
        # 'S21.G00.30.012': '',  # Code de distribution à l'étranger
        'S21.G00.30.014': 'birth_department',
        # 'S21.G00.30.015': '',  # Code pays de naissance
        # 'S21.G00.30.016': '',  # Complément de la localisation
        # 'S21.G00.30.017': '',  # Service de distribution, complément de loc.
        # 'S21.G00.30.019': '',  # Matricule de l'individu dans l'entreprise
        # 'S21.G00.30.020': '',  # Numéro technique temporaire

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


        # BLOC RÉGULARISATION DU PRÉLÈVEMENT À LA SOURCE : TODO

        # 'S21.G00.56.001': '', #   Mois de l'erreur O
        # 'S21.G00.56.002': '', #   Type d'erreur O

        # Régularisation de la rémunération nette fiscale C
        # 'S21.G00.56.003': '',

        # Rémunération nette fiscale déclarée le mois de l’erreur C
        # 'S21.G00.56.004': '',

        #   Régularisation du taux de prélèvement à la source C
        # 'S21.G00.56.005': '',

        #   Taux déclaré le mois de l’erreur C
        # 'S21.G00.56.006': '',

        #   Montant de la régularisation du prélèvement à la source O
        # 'S21.G00.56.007': '',
    }

    translations = {
        'gender': {'male': u'01', 'female': u'02'}
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
        account_ids = [x.invoice_account.id
            for x in Tax.search([('type', '=', 'pasrau_rate')])]

        associated_lines = MoveLine.search([
                ('principal_invoice_line.invoice', '=', self.origin.id),
                ('account', 'in', account_ids),
                ])

        def keyfunc(line):
            return line.origin.party

        sorted_lines = sorted(associated_lines, key=keyfunc)

        data = {'individuals': {}}
        for party, grouped_lines in groupby(sorted_lines, key=keyfunc):
            data['individuals'][party] = {'lines': list(grouped_lines)}

        individuals_at_zero = self.fetch_individuals_at_zero(associated_lines,
            data['individuals'])
        assert not any(x in data['individuals'] for x in individuals_at_zero)

        data['individuals'].update({x: {'lines': [0]}
            for x in individuals_at_zero})
        self.data = data
        if not self.data['individuals']:
            self.void = True

    def fetch_individuals_at_zero(self, associated_lines, slip_parties):
        cursor = Transaction().connection.cursor()
        pool = Pool()
        move = pool.get('account.move').__table__()
        move_line = pool.get('account.move.line').__table__()
        Party = pool.get('party.party')
        party = Party.__table__()
        invoice = pool.get('account.invoice').__table__()
        invoice_line = pool.get('account.invoice.line').__table__()
        account_tax = pool.get('account.tax').__table__()
        claim = pool.get('claim').__table__()
        indemnification = pool.get('claim.indemnification').__table__()
        loss = pool.get('claim.loss').__table__()
        service = pool.get('claim.service').__table__()
        line_claim_detail = pool.get('account.invoice.line.claim_detail'
            ).__table__()
        product = pool.get('product.product').__table__()
        template = pool.get('product.template').__table__()
        supplier_tax = pool.get('product.template-supplier-account.tax'
            ).__table__()

        query_table = move_line.join(move, condition=(
                move_line.move == move.id)
            ).join(invoice, condition=(
                invoice.move == move.id)
            ).join(invoice_line, condition=(
                invoice_line.invoice == invoice.id)
            ).join(line_claim_detail, condition=(
                line_claim_detail.invoice_line == invoice_line.id)
            ).join(indemnification, condition=(
                line_claim_detail.indemnification == indemnification.id)
            ).join(party, condition=(
                indemnification.beneficiary == party.id)
            ).join(service, condition=(
                indemnification.service == service.id)
            ).join(loss, condition=(
                service.loss == loss.id)
            ).join(claim, condition=(
                loss.claim == claim.id)
            ).join(product, condition=(
                invoice_line.product == product.id)
            ).join(template, condition=(
                product.template == template.id)
            ).join(supplier_tax, condition=(
                template.id == supplier_tax.product)
            ).join(account_tax, condition=(
                supplier_tax.tax == account_tax.id)
            )

        where_clause = ((claim.status.in_(['open', 'reopen']))
            & (invoice.state == 'paid')
            & (invoice.business_kind == 'claim_invoice')
            & (account_tax.type == 'pasrau_rate')
            & (party.is_person == True)
            & (service.annuity_frequency != Null))

        associated_move_lines = [x.id for x in associated_lines]

        if associated_move_lines:
            where_clause &= (Not(
                move_line.id.in_([x.id for x in associated_lines])))

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
            return self.data['individuals'].keys()
        elif block_id == 'S21.G00.50':
            return self.data['individuals'][parent]['lines']
        else:
            return super(NEORAUTemplate, self).get_instances(block_id, parent)

    @property
    def declaration_nature(self):
        return u'11'

    @property
    def fraction_number(self):
        return u'10'

    @property
    def declaration_rank(self):
        # TODO : sequence starting at zero each month
        return u'0'

    @property
    def declaration_month(self):
        return unicode(self.origin.invoice_date.strftime('01%m%Y'))

    def custom_dgfip(self, slip):
        return u'DGFiP'

    def custom_pasrau_bic(self, slip):
        return slip.company.party.bank_accounts[0].bank.bic

    def custom_pasrau_iban(self, slip):
        return slip.company.party.bank_accounts[0].number

    def custom_pasrau_total_amount(self, slip):
        return slip.total_amount if slip.total_amount else Decimal('0')

    def custom_pasrau_slip_end_date(self, slip):
        return slip.invoice_date + relativedelta(months=1, days=-1)

    def custom_pasrau_payment_mode(self, slip):
        return u'05'  # This means sepa direct debit

    def custom_gender(self, party):
        return self.translations['gender'][party.gender]

    def custom_birth_place(self, party):
        return u'SLN'

    def custom_birth_department(self, party):
        return u'00'

    def get_pasrau_tax_line(self, line):
        invoice = line.origin
        for tax_line in invoice.taxes:
            if tax_line.tax.invoice_account == line.account:
                return tax_line

    def custom_pasrau_reconciliation_date(self, line):
        if line == 0:
            return self.origin.invoice_date
        return line.origin.reconciliation_date

    def custom_pasrau_base(self, line):
        if line == 0:
            return Decimal('0.0')
        return self.get_pasrau_tax_line(line).base

    def custom_pasrau_debit_amount(self, line):
        if line == 0:
            return Decimal('0.0')
        return self.get_pasrau_tax_line(line).amount * -1

    def get_potential_personalized_rate(self, line):
        PartyCustomPasrauRate = Pool().get('party.pasrau.rate')
        invoice_date = line.origin.tax_date
        candidates = PartyCustomPasrauRate.search([
                ('party', '=', line.origin.party.id),
                ('create_date', '<=', line.origin.create_date),
                ('effective_date', '<=', invoice_date)],
            order=[('effective_date', 'ASC')])
        if candidates:
            return candidates[-1]

    def custom_pasrau_rate(self, line):
        # TODO: this should be stored somewhere
        # for now, we try to re-calculate
        if line == 0:
            return Decimal('0.0')
        DefaultPasrauRate = Pool().get('claim.pasrau.default.rate')
        rate = None
        perso_rate = self.get_potential_personalized_rate(line)
        if perso_rate:
            rate = perso_rate.pasrau_tax_rate
        else:
            pasrau_data = line.origin._build_pasrau_dict()
            zip_code = line.origin.party.main_address.zip
            rate = DefaultPasrauRate.get_appliable_default_pasrau_rate(zip_code,
                pasrau_data['income'], pasrau_data['period_start'],
                pasrau_data['period_end'], pasrau_data['invoice_date'])
        return rate * 100

    def custom_pasrau_rate_kind(self, line):
        if line == 0:
            return u'99'
        DefaultPasrauRate = Pool().get('claim.pasrau.default.rate')
        perso_rate = self.get_potential_personalized_rate(line)
        if perso_rate:
            return u'01'
        region = DefaultPasrauRate.get_region(
            line.origin.party.main_address.zip)
        return {
            'metropolitan': u'17',
            'grm': u'27',
            'gm': u'37',
            }.get(region)

    def custom_pasrau_rate_id(self, line):
        return u'-1'  # TODO : should be stored on perso rate from DGFIP crm


class NEORAU(dsn.NEODES):

    def get_resource_file_name(self, kind):
        # The files below are the "Fields", "Data Types", "Blocks" tab from
        # https://www.net-entreprises.fr/wp-content/uploads/2018/06/
        # PASRAU-tableau-categories-datatypes-2017.6.xlsx
        # encoding is utf8
        # I renamed the "Nature" column to "Name" in the datatypes file
        # to match dsn Spec
        return 'PASRAU-tableau-categories-datatypes-2017.6_%s.csv' % kind
