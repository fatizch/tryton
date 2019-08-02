# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import itertools
import os.path
import traceback
from dateutil.parser import parse
from decimal import Decimal
from functools import lru_cache
from lxml import etree

from trytond.pool import Pool
from trytond.modules.coog_core import batch, utils
from trytond.transaction import Transaction


NAMESPACES = {
    'a': "http://www.almerys.com/",
    }


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
    def select_ids(cls, in_directory, error_directory):
        files = cls.get_file_names_and_paths(in_directory)
        handler = AlmerysActuariatHandler()
        claims = []
        for file_name, file_path in files:
            claims.append((handler.parse(file_path, cls.kind),))
        return claims

    @classmethod
    def convert_to_instances(cls, ids, *args, **kwargs):
        return [x[0][0] for x in ids]

    @classmethod
    def log_error(cls, directory, filename, error, traceback):
        error_fn = os.path.join(directory, filename + '.error')
        # The file must exists to be locked
        if not os.path.exists(error_fn):
            with open(error_fn, 'a'):
                pass
        with utils.FileLocker(error_fn, 'a') as file:
            file.write(str(error))
            file.write('\n')
            file.write(traceback)
            file.write('\n')


class AlmerysClaimIndemnification(AlmerysXMLBatchMixin):
    "Almerys Claim Indemnification"
    __name__ = 'claim.almerys.claim_indemnification'
    kind = 'decomptes'

    @classmethod
    def execute(cls, objects, ids, in_directory, error_directory):
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
                    Indemnification.invoice(indemnifications)
            except Exception as e:
                tb = traceback.format_exc()
                cls.log_error(error_directory, claim_e['file'], e, tb)

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
            health_loss.almerys_num_dents = int(loss_e['numDents'])
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
        if claim.claimant != contract.subscriber:
            raise AlmerysError("Claimant different than subscriber")
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
            code = element['idDecompte'] + '-' + loss['numLigneFacture']
            loss2amount[code] = get_amount(loss['mtRemboursementRC'])
            loss2prescriber[code] = loss['prescriber']
        for loss in claim.losses:
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
            cls, product, positive_amount, negative_amount,
            positive_services, negative_services):
        pool = Pool()
        InvoiceLine = pool.get('account.invoice.line')

        p_line = InvoiceLine(
            type='line',
            quantity=1,
            product=product,
            almerys_services=positive_services,
            )
        p_line.on_change_product()
        p_line.unit_price = positive_amount

        n_line = InvoiceLine(
            type='line',
            quantity=1,
            product=product,
            almerys_cancelled_services=negative_services
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
    def select_ids(cls, in_directory, out_directory, error_directory):
        payments = super().select_ids(in_directory, error_directory)
        files = cls.get_file_names_and_paths(in_directory)
        cls.archive_treated_files(files, out_directory, utils.today())
        return payments

    @classmethod
    def execute(cls, objects, ids, in_directory, out_directory,
                error_directory):
        pool = Pool()
        AlmerysConfig = pool.get('third_party_protocol.almerys.configuration')
        Statement = pool.get('account.statement')

        filename = objects[0]['file'] if objects else ''
        try:
            config = AlmerysConfig(1)
            statements = []
            for payment in objects:
                lines = cls.get_statement_lines(payment)
                statement = Statement(
                    date=utils.today(),
                    journal=config.claim_statement_journal,
                    lines=lines,
                    name=payment['idFlux'],
                    number_of_lines=len(lines),
                    )
                statements.append(statement)

            if statements:
                Statement.save(statements)
                Statement.validate_statement(statements)
                Statement.post(statements)
        except Exception as e:
            tb = traceback.format_exc()
            cls.log_error(error_directory, filename, e, tb)

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
        adherent = get_party(payment['idAdherent'])
        invoice_number = payment['idPaiement'][:-9]
        claim, = Claim.search([
                ('invoice_number', '=', invoice_number),
                ])
        lines = []
        for invoice in claim.invoices:
            line = StatementLine()
            line.account = config.account_statement
            line.amount = invoice.total_amount
            line.date = get_date(payment['dtVirement'])
            line.number = payment['idPaiement']
            line.description = description
            line.party_payer = adherent
            line.invoice = invoice
            indemnifications = {detail.indemnification
                for il in invoice.lines
                for detail in il.claim_details}
            assert len(indemnifications) == 1
            indemnification = indemnifications.pop()
            line.party = indemnification.service.loss.covered_element.party
            lines.append(line)

        statement_amount = get_amount(payment['mtReglementTTC'])
        if statement_amount != sum(l.amount for l in lines):
            raise AlmerysError(
                "Amount does not match invoices for claim '%s'" % claim.name)

        return lines
