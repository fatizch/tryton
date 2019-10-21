# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import csv
import datetime
import itertools
import os.path
import traceback
from dateutil.parser import parse
from decimal import Decimal
from functools import lru_cache
from lxml import etree
from collections import defaultdict

from trytond.pool import Pool
from trytond.modules.coog_core import batch, utils, coog_string
from trytond.transaction import Transaction


NAMESPACES = {
    'a': "http://www.almerys.com/",
    }

__all__ = [
    'AlmerysClaimIndemnification',
    'AlmerysStatementCreation',
    'AlmerysPaybackCreation',
    ]


ALMERYS_PAYBACK_REASONS = (
    'almerys_erreur_de_taux',
    'almerys_facture_annulee',
    'almerys_trop_percu',
    'almerys_prestations_non_realisees',
    'almerys_erreur_destinataire_de_paiement',
    'almerys_erreur_beneficiaire',
    'almerys_100_ro',
    'almerys_cmu',
    'almerys_erreur_de_valorisation',
    'almerys_l’adherent_a_regle',
    'almerys_pas_de_droit_tp_pour_cette_prestation',
    'almerys_facture_acte_payee_deux_fois',
    'almerys_utilisation_carte_tp_perimee',
    'almerys_erreur_technique',
    'almerys_non_respect_de_la_convention',
    'almerys_facture_payee_sous_deux_identifications_differentes',
    'almerys_facture_payee_sous_deux_numeros_de_facture_differents'
    )


def get_text(path, element):
    if not path.endswith('/text()'):
        path += '/text()'
    txt = element.xpath(path, namespaces=NAMESPACES, smart_strings=False)
    return txt[0] if txt else None


def get_amount(amount_str):
    return Decimal(amount_str) if amount_str else None


def get_date(date_str):
    return parse(date_str).date() if date_str else None


def get_bool(bool_str):
    return bool_str == 'true'


@lru_cache()
def get_party(code):
    pool = Pool()
    Party = pool.get('party.party')

    party, = Party.search([('code', '=', code)])
    return party.id


class AlmerysActuariatHandler:

    def parse(self, fpath, kind):
        current_file = os.path.basename(fpath)
        self.kind = kind
        self.header_data = {}
        a_elements = []
        with open(fpath, 'rb') as source:
            for event, element in etree.iterparse(source):
                a_element = self.handle(event, element)
                if a_element:
                    new_element = self.header_data.copy()
                    new_element.update(a_element)
                    new_element['file'] = current_file
                    a_elements.append(new_element)
        return a_elements

    def handle(self, event, element):
        tag = etree.QName(element)

        if tag.localname == 'idFlux':
            self.header_data['idFlux'] = element.text.strip()
        elif self.kind == tag.localname == 'decomptes':
            return self.get_claim_data(element)
        elif self.kind == tag.localname == 'paiements':
            return self.get_statement_data(element)
        elif self.kind == tag.localname == 'indus':
            return self.get_payback_data(element)

    def _get_data(self, element, specs):
        data = {}
        for key in specs:
            data[key] = get_text('./a:' + key, element)
        return data

    def get_claim_data(self, element):
        claim = self._get_data(element, {
                'typeFlux', 'idDecompte', 'dtArrivee',
                'numContrat', 'dtArrivee', 'numFacture', 'dtComptable',
                })
        claim['claimant_code'] = get_text(
            './a:membrePaye/a:idAdherent', element)
        claim['actes'] = []
        for loss_e in element.xpath('./a:actes', namespaces=NAMESPACES):
            loss = self._get_data(loss_e, {
                    'numLigneFacture', 'dt1Soin', 'dt2Soin', 'nombreActe',
                    'mtRemboursementRC', 'mtBaseRemboursement',
                    'txRemboursementRO', 'mtRemboursementRO',
                    'mtDepenseReelle', 'mtRemboursementAutresMut',
                    'dtPrescription', 'dtPrescription', 'dtAccident',
                    'topDepassement', 'mtDepassement', 'numDents',
                    'coefActe', 'topParcoursSoin', 'ContratAccesSoins',
                    'cdRegrpmtActeFamille', 'lblRegrpmtActeFamille',
                    'codeActe', 'lblActe',
                    })
            loss['covered_person'] = get_text(
                './a:beneficiaire/a:idBeneficiaire', loss_e)
            loss['prescriber'] = get_text('./a:prescripteur/a:nom', loss_e)
            claim['actes'].append(loss)
        return claim

    def get_statement_data(self, element):
        data = self._get_data(element, {
                'mtReglementTTC', 'dtVirement', 'iban', 'modePaiment',
                'designationBancaire', 'idPaiement', 'idAdherent',
                })
        return data

    def get_payback_data(self, element):
        parent = self._get_data(element, {'numFacture', 'montantTotIndu',
                'mtTotalRemboursementRC',
                })
        parent['actes'] = []
        for loss_e in element.xpath('./a:actes', namespaces=NAMESPACES):
            loss = self._get_data(loss_e, {
                    'numLigneFacture', 'mtRemboursementRC',
                    })
            loss['paybacks'] = []
            for payback_e in element.xpath('./a:actes/a:indu',
                    namespaces=NAMESPACES):
                payback = self._get_data(payback_e, {
                        'mtIndu', 'commentIndu', 'causeIndu', 'typeIndu'
                        })
                loss['paybacks'].append(payback)
            parent['actes'].append(loss)
        return parent


class AlmerysError(Exception):
    pass


class AlmerysXMLBatchMixin(batch.BatchRootNoSelect):
    kind = None

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._default_config_items.update({
                'split': False,
                'job_size': 1,
                })

    @classmethod
    def select_ids(cls, in_directory, out_directory, error_directory):
        files = cls.get_file_names_and_paths(in_directory)
        handler = AlmerysActuariatHandler()
        claims = []
        for file_name, file_path in files:
            for claim in handler.parse(file_path, cls.kind):
                claims.append((claim,))
        cls.archive_treated_files(files, out_directory, utils.today())
        return claims

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return [x[0] for x in ids]

    @classmethod
    def log_error(cls, label, directory, filename, error, traceback):
        error_fn = os.path.join(directory, filename + '.error.csv')
        # The file must exists to be locked
        if not os.path.exists(error_fn):
            with open(error_fn, 'a'):
                pass
        with utils.FileLocker(error_fn, 'a') as file:
            error_csv_writer = csv.writer(file, delimiter=';')
            error_csv_writer.writerow([label,
                    str(error) + '\n' + traceback])


class AlmerysClaimIndemnification(AlmerysXMLBatchMixin):
    "Almerys Claim Indemnification"
    __name__ = 'claim.almerys.claim_indemnification'
    kind = 'decomptes'

    @classmethod
    def execute(cls, objects, ids, in_directory, out_directory,
            error_directory):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')

        for claim_e in objects:
            try:
                claim = cls.get_claim(claim_e)
                claim.save()

                cls.deliver_services(claim)
                if claim.third_party_payment:
                    cls.create_tp_invoices(claim, claim_e)
                else:
                    indemnifications = cls.get_indemnifications(claim, claim_e)
                    Indemnification.do_calculate(indemnifications)
                    Indemnification.save(indemnifications)
                    Indemnification.control_indemnification(indemnifications)
                    Indemnification.validate_indemnification(indemnifications)
                    Indemnification.invoice(indemnifications)
            except Exception as e:
                tb = traceback.format_exc()
                cls.log_error('Sinistre ' + claim_e['idDecompte'],
                    error_directory, claim_e['file'], e, tb)

    @classmethod
    def get_claim(cls, claim_e):
        pool = Pool()
        Claim = pool.get('claim')
        Loss = pool.get('claim.loss')
        HealthLoss = pool.get('claim.loss.health')
        LossDesc = pool.get('benefit.loss.description')
        EventDesc = pool.get('benefit.event.description')
        Contract = pool.get('contract')
        ModelData = pool.get('ir.model.data')

        is_tp = claim_e['typeFlux'] == 'TP'
        claim_number = claim_e['idDecompte']
        if Claim.search([('name', '=', claim_number)]):
            raise AlmerysError("Duplicate claim '{}'".format(claim_number))

        losses = []
        for loss_e in claim_e['actes']:
            health_loss = HealthLoss()
            health_loss.covered_person = get_party(loss_e['covered_person'])
            health_loss.act_date = get_date(loss_e['dt1Soin'])
            health_loss.act_end_date = get_date(loss_e['dt2Soin'])
            health_loss.quantity = int(loss_e['nombreActe'])
            health_loss.ss_agrement_price = get_amount(
                loss_e['mtBaseRemboursement'])
            health_loss.ss_agrement_rate = get_amount(
                loss_e['txRemboursementRO'])
            health_loss.ss_reimbursement_amount = get_amount(
                loss_e['mtRemboursementRO'])
            health_loss.total_charges = get_amount(
                loss_e['mtDepenseReelle'])
            health_loss.almerys_other_insurer_delivered_amount = get_amount(
                loss_e['mtRemboursementAutresMut'])
            health_loss.almerys_prescription_date = get_date(
                loss_e['dtPrescription'])
            health_loss.almerys_accident_date = get_date(
                loss_e['dtAccident'])
            health_loss.almerys_top_depassement = get_bool(
                loss_e['topDepassement'])
            health_loss.almerys_depassement_amount = get_amount(
                loss_e['mtDepassement'])
            health_loss.almerys_num_dent = loss_e['numDents'] or ''
            health_loss.act_coefficient = get_amount(loss_e['coefActe'])
            health_loss.is_off_care_pathway = not get_bool(
                loss_e['topParcoursSoin'])
            health_loss.is_care_access_contract = get_bool(
                loss_e['ContratAccesSoins'])

            act_family_code = loss_e['cdRegrpmtActeFamille']
            act_family_label = loss_e['lblRegrpmtActeFamille']
            act_code = loss_e['codeActe']
            act_label = loss_e['lblActe']
            health_loss.act_description = cls._get_act(
                act_code, act_label, act_family_code, act_family_label)

            loss = Loss()
            loss.code = (claim_number + '-' + loss_e['numLigneFacture'])
            loss.health_loss = [health_loss]
            desc_code = 'TP' if is_tp else 'HTP'
            loss.loss_desc, = LossDesc.search([('code', '=', desc_code)])
            loss.event_desc, = EventDesc.search([('code', '=', desc_code)])
            loss.start_date = get_date(loss_e['dt1Soin'])
            loss.state = 'active'
            loss.covered_person = health_loss.covered_person
            loss.is_a_relapse = False
            loss.almerys_sequence = int(loss_e['numLigneFacture'])

            losses.append(loss)

        if not losses:
            raise AlmerysError("No losses in claim '{}'".format(claim_number))

        claim = Claim()
        claim.name = claim_number
        claim.company = Transaction().context['company']
        claim.declaration_date = get_date(claim_e['dtArrivee'])
        claimant_code = claim_e['claimant_code']
        claim.claimant = get_party(claimant_code)
        claim.invoice_number = claim_e['numFacture']
        claim.invoice_date = get_date(claim_e['dtComptable'])
        claim.third_party_payment = is_tp
        claim.losses = losses
        claim.is_almerys = True
        claim.almerys_file = claim_e['file']

        contract_number = claim_e['numContrat']
        contract, = Contract.search([
                ('contract_number', '=', contract_number),
                ])
        claim.main_contract = contract
        claim.status = 'closed'
        claim.sub_status = ModelData.get_id(
            'claim_almerys', 'claim_sub_status_almerys')

        return claim

    @classmethod
    @lru_cache()
    def _get_act(cls, code, label, family_code, family_label):
        pool = Pool()
        MedicalActDescription = pool.get('benefit.act.description')

        acts = MedicalActDescription.search([('code', '=', code)])
        if not acts:
            family = cls._get_act_family(family_code, family_label)
            act = MedicalActDescription(code=code, name=label, family=family)
            act.save()
        elif len(acts) == 1:
            act = acts[0]
        else:
            raise AlmerysError("Too many medical act match code '%s'" % code)
        return act.id

    @classmethod
    @lru_cache()
    def _get_act_family(cls, code, label):
        pool = Pool()
        Family = pool.get('benefit.act.family')

        families = Family.search([('code', '=', code)])
        if not families:
            family = Family(code=code, name=label)
            family.save()
        elif len(families) == 1:
            family, = families
        else:
            raise AlmerysError("Too many Benefit Description match '%s'" % code)
        return family.id

    @classmethod
    def deliver_services(cls, claim):
        pool = Pool()
        Service = pool.get('claim.service')
        TPPeriod = pool.get('contract.option.third_party_period')

        to_save = []
        periods = TPPeriod.search([
                ('protocol.technical_protocol', '=', 'almerys'),
                ('option.covered_element.contract', '=',
                    claim.main_contract.id),
                ('status', '=', 'sent'),
                ])
        for period in periods:
            for loss in claim.losses:
                if (loss.covered_person !=
                        period.option.covered_element.party):
                    continue
                if ((period.end_date is not None
                            and loss.start_date > period.end_date)
                        or (loss.start_date < period.start_date)):
                    continue
                benefit_attr = 'almerys_benefit_' + (
                    'tp' if claim.third_party_payment else 'htp')
                benefit = getattr(period.option.coverage, benefit_attr)
                loss.init_services(period.option, [benefit])
                to_save.extend(loss.services)
        if to_save:
            Service.save(to_save)

    @classmethod
    def get_indemnifications(cls, claim, element):
        pool = Pool()
        Indemnification = pool.get('claim.indemnification')

        indemnifications = []
        loss2amount, loss2prescriber = {}, {}
        for loss in element['actes']:
            code = element['numFacture'] + '-' + loss['numLigneFacture']
            loss2amount[code] = get_amount(loss['mtRemboursementRC'])
            loss2prescriber[code] = loss['prescriber']
        for loss in claim.losses:
            if not loss.services:
                continue
            service, = loss.services
            journal, = service.benefit.payment_journals
            health_loss, = loss.health_loss
            currency = service.get_currency()
            indemnification = Indemnification(
                journal=journal,
                service=service,
                start_date=health_loss.act_date,
                end_date=health_loss.act_end_date,
                forced_base_amount=loss2amount[loss.code],
                currency=currency,
                local_currency=currency,
                local_currency_amount=loss2amount[loss.code],
                beneficiary=loss.covered_person,
                beneficiary_as_text=loss2prescriber[loss.code],
                manual=True,
                status='controlled'
                )
            Indemnification.update_product(indemnification)
            indemnifications.append(indemnification)
        return indemnifications

    @classmethod
    def _group_loss_key(cls, loss):
        service, = loss.services
        return (
            ('product', service.benefit.products[0]),
            )

    @classmethod
    def _create_tp_invoice_lines(
            cls, invoice, product, positive_amount, negative_amount,
            positive_services, negative_services):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        p_line = InvoiceLine(
            invoice=invoice,
            type='line',
            quantity=1,
            product=product,
            almerys_services=positive_services,
            )
        p_line.on_change_product()
        p_line.unit_price = positive_amount

        n_line = InvoiceLine(
            invoice=invoice,
            type='line',
            quantity=1,
            product=product,
            almerys_payback_services=negative_services
            )
        n_line.on_change_product()
        n_line.unit_price = negative_amount

        return [p_line, n_line]

    @classmethod
    def create_tp_invoices(cls, claim, element):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        AlmerysConfig = pool.get('third_party_protocol.almerys.configuration')

        config = AlmerysConfig(1)
        party = config.invoiced_party

        invoice = Invoice(
            business_kind='third_party_management',
            type='in',
            company=claim.company,
            journal=config.claim_journal,
            party=party,
            invoice_address=party.address_get(type='invoice'),
            currency=claim.company.currency,
            account=party.account_payable_used,
            payment_term=party.supplier_payment_term,
            invoice_date=utils.today(),
            currency_date=utils.today(),
            )
        invoice_lines = []
        losses = []
        loss2amount = {}
        losses.extend(claim.losses)
        for loss in element['actes']:
            code = element['idDecompte'] + '-' + loss['numLigneFacture']
            loss2amount[code] = get_amount(loss['mtRemboursementRC'])
        losses.sort(key=cls._group_loss_key)
        for loss_key, grouped_losses in itertools.groupby(
                losses, cls._group_loss_key):
            loss_key = dict(loss_key)
            positive_amount, negative_amount = Decimal(0), Decimal(0)
            positive_services, negative_services = [], []
            for loss in grouped_losses:
                amount = loss2amount[loss.code]
                if amount < 0:
                    negative_amount += amount
                    negative_services.extend(list(loss.services))
                else:
                    positive_amount += amount
                    positive_services.extend(list(loss.services))
            p_line, n_line = cls._create_tp_invoice_lines(
                invoice,
                loss_key['product'],
                invoice.currency.round(positive_amount),
                invoice.currency.round(negative_amount),
                positive_services, negative_services)
            invoice_lines.extend(filter(None, [p_line, n_line]))

        if not invoice_lines:
            raise AlmerysError(
                "No invoice line for claim '{}'".format(claim.name))

        invoice.lines = invoice_lines
        invoice.save()
        Invoice.post([invoice])


class AlmerysStatementCreation(AlmerysXMLBatchMixin):
    "Almerys Statement Creation"
    __name__ = 'claim.almerys.statement_creation'
    kind = 'paiements'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._default_config_items.update({
                'split': False,
                'job_size': 0,
                })

    @classmethod
    def execute(cls, objects, ids, in_directory, out_directory,
                error_directory):
        pool = Pool()
        AlmerysConfig = pool.get('third_party_protocol.almerys.configuration')
        Statement = pool.get('account.statement')

        def group_by_file(payment):
            return payment['file']

        objects = sorted(objects, key=group_by_file)
        for filename, payments in itertools.groupby(objects, key=group_by_file):
            try:
                config = AlmerysConfig(1)
                all_lines = []
                for payment in payments:
                    lines = cls.get_statement_lines(payment)
                    if not lines:
                        continue
                    else:
                        all_lines.extend(lines)
                if all_lines:
                    statement = Statement(
                        date=utils.today(),
                        journal=config.claim_statement_journal,
                        lines=all_lines,
                        name=payment['idFlux'],
                        number_of_lines=len(all_lines),
                        )
                    statement.save()
                    Statement.validate_statement([statement])
                    Statement.post([statement])
            except Exception as e:
                tb = traceback.format_exc()
                cls.log_error('Relevé', error_directory, filename, e, tb)

    @classmethod
    def get_statement_lines(cls, payment):
        pool = Pool()
        StatementLine = pool.get('account.statement.line')
        AlmerysConfig = pool.get('third_party_protocol.almerys.configuration')
        Claim = pool.get('claim')

        config = AlmerysConfig(1)
        description = """
IBAN: {iban}
Mode Paiement: {modePaiment}
Designation Bancaire: {designationBancaire}
        """.format(**payment)
        invoice_number = payment['idPaiement'][:-9]
        claim, = Claim.search([
                ('invoice_number', '=', invoice_number),
                ])
        if claim.third_party_payment:
            return []
        lines = []
        for invoice in claim.invoices:
            line = StatementLine()
            line.amount = -invoice.total_amount
            line.date = get_date(payment['dtVirement'])
            line.number = payment['idPaiement']
            line.description = description
            line.party_payer = config.invoiced_party
            line.invoice = invoice
            line.account = invoice.account
            line.party = invoice.party
            lines.append(line)

        statement_amount = get_amount(payment['mtReglementTTC'])
        if statement_amount != -sum(l.amount for l in lines):
            raise AlmerysError(
                "Amount does not match invoices for claim '%s'" % claim.name)

        return lines


class AlmerysPaybackCreation(AlmerysXMLBatchMixin):
    'Payback Almerys Batch'
    __name__ = 'claim.almerys.payback_creation'
    kind = 'indus'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._default_config_items.update({
                'split': False,
                'job_size': 1,
                })

    @classmethod
    def get_last_indemnification(cls, loss):
        loss_paid_indemnifications = sorted([indemn
                for service in loss.services
                for indemn in service.indemnifications
                if indemn.status == 'paid'
                and not all(d.kind == 'deductible' for d in indemn.details)],
            key=lambda x: (x.end_date or x.start_date or datetime.date.min),
            reverse=True)
        if not loss_paid_indemnifications:
            raise AlmerysError("No paid indemnifications have been found for "
                "loss with code '{}'".format(loss.code))
            return
        return loss_paid_indemnifications[0]

    @classmethod
    def create_indemnification(cls, payback, loss, last_indemn_amount):
        Indemnification = Pool().get('claim.indemnification')
        service, = loss.services
        journal, = service.benefit.payment_journals
        health_loss, = loss.health_loss
        currency = service.get_currency()
        amount = last_indemn_amount - get_amount(payback['mtIndu'])
        indemnification = Indemnification(
            journal=journal,
            service=service,
            start_date=health_loss.act_date,
            end_date=health_loss.act_end_date,
            forced_base_amount=amount,
            currency=currency,
            beneficiary=loss.covered_person,
            manual=True,
            status='controlled',
            control_reason='',
            note=payback['commentIndu'] or '' + '\n',
            payback_method='immediate',
            payment_term=None,
            product=service.benefit.products[0],
            local_currency=currency,
            local_currency_amount=amount,
            )
        Indemnification.update_product(indemnification)
        return indemnification

    @classmethod
    def create_tp_invoice(cls):
        pool = Pool()
        Invoice = pool.get('account.invoice')
        AlmerysConfig = pool.get('third_party_protocol.almerys.configuration')
        Company = pool.get('company.company')
        config = AlmerysConfig(1)
        party = config.invoiced_party
        company = Company(Transaction().context['company'])
        return Invoice(
            business_kind='third_party_management',
            type='in',
            company=company.id,
            journal=config.claim_journal,
            party=party,
            invoice_address=party.address_get(type='invoice'),
            currency=company.currency,
            account=party.account_payable_used,
            payment_term=party.supplier_payment_term,
            invoice_date=utils.today(),
            currency_date=utils.today()
            )

    @classmethod
    def create_tp_invoice_line(cls, payback, loss, invoice, last_indemn_amount):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')
        amount = -(last_indemn_amount - get_amount(payback['mtIndu']))
        service, = loss.services
        product = service.benefit.products[0]
        invoice_line = InvoiceLine(
            invoice=invoice,
            type='line',
            quantity=1,
            product=product,
            almerys_payback_services=[service])
        invoice_line.on_change_product()
        invoice_line.unit_price = amount
        return invoice_line

    @classmethod
    def finalize_indemnifications(cls, indemnifications_to_cancel,
            payback_indemnifications):
        pool = Pool()
        Indemnification = Pool().get('claim.indemnification')
        PaybackReason = pool.get('claim.indemnification.payback_reason')
        payback_reasons = {p.code: p for p in
            PaybackReason.search([('code', 'in', ALMERYS_PAYBACK_REASONS)])
            }
        cancelled_indemnifications = []
        for key, value in indemnifications_to_cancel.items():
            payback_reason = (payback_reasons[key]
                if key in ALMERYS_PAYBACK_REASONS else None)
            Indemnification.cancel_indemnification(value,
                payback_reason=payback_reason)
            cancelled_indemnifications.extend(value)
        Indemnification.do_calculate(payback_indemnifications)
        Indemnification.save(payback_indemnifications)
        Indemnification.control_indemnification(payback_indemnifications +
            cancelled_indemnifications)
        Indemnification.validate_indemnification(payback_indemnifications +
            cancelled_indemnifications)
        Indemnification.invoice(payback_indemnifications +
            cancelled_indemnifications)

    @classmethod
    def execute(cls, objects, ids, in_directory, out_directory,
            error_directory):
        pool = Pool()
        Loss = Pool().get('claim.loss')
        Invoice = pool.get('account.invoice')
        for parent_e in objects:
            tp_invoice_lines = []
            indemnifications_to_cancel = defaultdict(list)
            payback_indemnifications = []
            try:
                losses_e = parent_e['actes']
                losses_codes = [parent_e['numFacture'] + '-' +
                    l['numLigneFacture'] for l in parent_e['actes']]
                losses = {l.code: l
                    for l in Loss.search([('code', 'in', losses_codes)])}
                tp_invoice = cls.create_tp_invoice()
                for loss_e in losses_e:
                    loss_code = parent_e['numFacture'] + '-' + \
                        loss_e['numLigneFacture']
                    if not losses.get(loss_code, None):
                        raise AlmerysError("No loss has been found with code "
                            "'{}'".format(loss_code))
                        continue
                    loss = losses[loss_code]
                    last_indemn_amount = cls.get_last_indemnification(
                        loss).amount
                    for payback in loss_e['paybacks']:
                        if not payback:
                            raise AlmerysError(
                                "No tag 'indu' found for loss with "
                                "code '{}'".format(loss_code))
                        payback_reason_code = 'almerys_' + coog_string.slugify(
                            payback['causeIndu'] or '')
                        if payback['typeIndu'] == 'HTP':
                            to_cancel = [indemn for service in loss.services
                                for indemn in service.indemnifications
                                if not ('cancel' in indemn.status)]
                            indemnifications_to_cancel[
                                payback_reason_code].extend(to_cancel)
                            payback_indemnifications.append(
                                cls.create_indemnification(
                                    payback, loss, last_indemn_amount))
                        elif payback['typeIndu'] == 'TP':
                            tp_invoice_lines.append(cls.create_tp_invoice_line(
                                    payback, loss, tp_invoice,
                                    last_indemn_amount))
                if payback_indemnifications:
                    cls.finalize_indemnifications(indemnifications_to_cancel,
                        payback_indemnifications)
                if tp_invoice_lines:
                    tp_invoice.lines = tp_invoice_lines
                    tp_invoice.save()
                    Invoice.post([tp_invoice])
            except Exception as e:
                tb = traceback.format_exc()
                cls.log_error('Facture ' + parent_e['file'], error_directory,
                    parent_e['file'], e, tb)
