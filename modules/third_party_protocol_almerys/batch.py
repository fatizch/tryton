# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime as dt

from lxml import etree
from lxml.builder import ElementMaker
from itertools import groupby
from operator import attrgetter
from stdnum import iban

from trytond.pool import Pool
from trytond.transaction import Transaction

from trytond.modules.coog_core import batch
from trytond.tools import grouped_slice

from . import return_almerys_hundler


__all__ = [
    'AlmerysReturnBatch',
    ]


def empty_element(e):
    return e is None or (isinstance(e, str) and e.strip() == '')


# This class allows to simplify instantion of elements by skipping those that
# are empty
class AlmerysElementMaker(ElementMaker):

    def __call__(self, tag, *children, **attributes):
        if children and all(empty_element(c) for c in children):
            return None
        sub_elements = []
        for child in children:
            if etree.iselement(child):
                sub_elements.append(child)
            elif child:
                sub_elements.append(str(child))
        return super().__call__(tag, *sub_elements, **attributes)


E = AlmerysElementMaker(nsmap={None: "http://www.almerys.com/NormeV3"})


class AlmerysProtocolBatch(batch.BatchRoot):
    "Almerys Batch Job"
    __name__ = 'third_party_protocol.batch.almerys'

    @classmethod
    def __setup__(cls):
        super().__setup__()
        cls._default_config_items.update({
                'split': False,
                'job_size': 1,
                'filepath_template': '%{BATCHNAME}/%{FILENAME}',
                })

    @classmethod
    def get_batch_main_model_name(cls):
        return 'contract.option.third_party_period'

    @classmethod
    def get_batch_search_model(cls):
        return 'contract.option.third_party_period'

    @classmethod
    def select_ids(cls, treatment_date, *args, **kwargs):
        pool = Pool()
        Contract = pool.get('contract')
        CoveredElement = pool.get('contract.covered_element')
        Option = pool.get('contract.option')
        TPPeriod = pool.get('contract.option.third_party_period')
        Protocol = pool.get('third_party_manager.protocol')

        contract = Contract.__table__()
        covered_element = CoveredElement.__table__()
        option = Option.__table__()
        tpperiod = TPPeriod.__table__()
        protocol = Protocol.__table__()

        cursor = Transaction().connection.cursor()
        cursor.execute(
            *contract
            .join(covered_element,
                condition=covered_element.contract == contract.id)
            .join(option,
                condition=option.covered_element == covered_element.id)
            .join(tpperiod,
                condition=tpperiod.option == option.id)
            .join(protocol,
                condition=tpperiod.protocol == protocol.id)
            .select(
                tpperiod.id,
                where=((tpperiod.status == 'waiting')
                    & (tpperiod.send_after < treatment_date)
                    & (protocol.technical_protocol == 'almerys')),
                order_by=[protocol.almerys_ss_groupe, contract.contract_number])
            )
        return [cursor.fetchall()]

    @classmethod
    def execute(cls, objects, ids, treatment_date, directory, **kwargs):
        pool = Pool()
        Sequence = pool.get('ir.sequence')
        TPPeriod = pool.get('contract.option.third_party_period')
        Config = pool.get('third_party_protocol.almerys.configuration')
        tp_prefix = 'third_party_protocol_almerys_'

        config = Config(1)
        sequence = Sequence.get_id(config.number_sequence_v3)
        now = dt.datetime.now()
        now = now.replace(microsecond=0)
        liens = {
            'child': 'EN',
            'parent': 'AE',
            'conjoint': 'CJ',
            'spouse': 'CJ',
            }

        perimetre_service = E.PERIMETRE_SERVICE()
        document = E.FICHIER(
            E.ENTETE(
                E.NUM_FICHIER(sequence),
                E.DATE_CREATION(now.isoformat()),
                E.VERSION_NORME(config.protocol_version),
                E.NUM_OS_EMETTEUR(config.customer_number),
                ),
            E.OFFREUR_SERVICE(
                E.LIBELLE_OS(config.customer_label),
                E.NUM_OS(config.customer_number),
                perimetre_service
                )
            )

        for _, periods in groupby(
                objects, lambda p: p.protocol.almerys_ss_groupe):
            periods = list(periods)
            protocol = periods[0].protocol
            perimetre_service.extend([
                    E.CODE_PERIMETRE(protocol.almerys_ss_groupe),
                    E.LIBELLE_PERIMETRE(protocol.almerys_libelle_ss_groupe)
                    ])

            def get_contract(period):
                return period.option.parent_contract

            for contract, periods in groupby(periods, get_contract):
                periods = list(periods)
                contract_e = E.CONTRAT(
                    E.NUM_CONTRAT(contract.contract_number),
                    E.ETAT_CONTRAT('OU'),
                    E.DATE_SOUSCRIPTION(
                        contract.initial_start_date.isoformat()),
                    E.DATE_IMMAT(contract.initial_start_date.isoformat()),
                    # DATE_RENOUVELLEMENT
                    )

                has_subscriber = any(
                    c.party == contract.subscriber
                    for c in contract.covered_elements)
                serialized_members = set()
                members = []
                rattachements = []
                services_tp_pec = []
                if not has_subscriber:
                    joignabilites = []
                    if contract.subscriber.almerys_joignabilite_adresse_media:
                        joignabilites.append(E.JOIGNABILITE(
                                E.MEDIA(contract.subscriber
                                    .almerys_joignabilite_media),
                                E.ADRESSE_MEDIA(contract.subscriber.email),
                                E.ACTIF('true')
                                ))
                    party_address = contract.subscriber.address_get()
                    if party_address:
                        idx = 0
                        line4 = party_address.address_lines.get('4_ligne4')
                        if not line4:
                            for idx in (3, 2, 5):
                                line4 = party_address.address_lines.get(
                                    '{}_ligne{}'.format(idx, idx))
                                if line4:
                                    break

                        party_address = E.ADRESSE_MEMBRE(
                            E.ADRESSE_AGREGEE(
                                E.LIGNE1('{} {}'.format(
                                        party_address.party.first_name,
                                        party_address.party.name)),
                                E.LIGNE2(party_address.address_lines.get(
                                    '2_ligne2', '') if idx != 2 else ''),
                                E.LIGNE3(party_address.address_lines.get(
                                    '3_ligne3', '') if idx != 3 else ''),
                                E.LIGNE4(line4),
                                E.LIGNE5(party_address.address_lines.get(
                                    '5_ligne5', '') if idx != 5 else ''),
                                E.LIGNE6('{} {}'.format(
                                        party_address.zip,
                                        party_address.city)),
                                E.LIGNE7(party_address.address_lines.get(
                                        '7_ligne7'))
                            ))
                    else:
                        party_address = None
                    membre = E.MEMBRE_CONTRAT(
                        E.SOUSCRIPTEUR('true'),
                        E.POSITION('01'),
                        E.TYPE_REGIME('RC'),
                        E.DATE_ENTREE(contract.initial_start_date.isoformat()),
                        E.INDIVIDU(
                            E.REF_INTERNE_OS(contract.subscriber.code),
                            E.DATE_NAISSANCE(
                                contract.subscriber.birth_date.isoformat()),
                            E.RANG_NAISSANCE(contract.subscriber.birth_order),
                            # COMMUNE_NAISSANCE
                            E.NOM_PATRONIMIQUE(contract.subscriber.birth_name
                                or contract.subscriber.name),
                            E.NOM_USAGE(contract.subscriber.name),
                            E.PRENOM(contract.subscriber.first_name),
                            E.CODE_SEXE(
                                'MA'
                                if contract.subscriber.gender == 'male'
                                else 'FE'),
                            E.PORTEUR_RISQUE(
                                contract.dist_network.name
                                if contract.dist_network
                                else '')
                            # PROFESSION
                            # MEDECIN_TRAITANT
                            # IDENTITE_WEB
                            # AUTRE
                            # REF_INTERNE_ALMERYS
                            # DATE_CAL
                            # TYPE_CAL
                            ),
                        party_address,
                        E.MEDIA_ENVOI(
                            E.RELEVE_PRESTA(
                                contract.subscriber.almerys_releve_presta),
                            E.COURRIER_GESTION(
                                contract.subscriber.almerys_courrier_gestion),
                            ),
                        *joignabilites,
                        # NUM_ADHESION
                        E.AUTONOME(
                            'true' if config.autonomous else 'false'),
                        # MODE_PAIEMENT
                        E.NNI(contract.subscriber.ssn_no_key[:13] or
                            contract.subscriber.main_insured_ssn[:13]),
                        E.NNI_RATT(
                            contract.subscriber.main_insured_ssn[:13]
                            if contract.subscriber.main_insured_ssn and
                            not contract.subscriber.ssn_no_key[:13] else ''),
                        )
                    membre.extend([
                            E.VIP('false'),
                            # DATE_CERTIFICATION_NNI
                            # DATE_CERTIFICATION_NNI_RATT
                            # DATE_DEBUT_SUSPENSION
                            # DATE_FIN_SUSPENSION
                            ])
                    if (contract.termination_reason ==
                            'unpaid_premium_termination'):
                        membre.extend([
                                E.DATE_RADIATION(
                                    contract.final_end_date.isoformat()),
                                E.MOTIF_RADIATION(
                                    'unpaid_premium_termination'),
                                ])
                    members.append(membre)
                for covered in contract.covered_elements:
                    option2periods = {}
                    for tp_period in periods:
                        if tp_period.option not in covered.options:
                            continue
                        option2periods.setdefault(
                            tp_period.option, []).append(tp_period)
                    for option in covered.options:
                        if option in option2periods:
                            continue
                        for o_period in option.third_party_periods:
                            if o_period.start_date <= now and (
                                    o_period.end_date is None
                                    or o_period.end_date > now):
                                option2periods.setdefault(
                                    option, []).append(o_period)
                                break
                    if not option2periods:
                        continue

                    for relation in covered.party.relations:
                        if relation.to == covered.contract.subscriber:
                            break
                    else:
                        relation = None

                    if covered.party not in serialized_members:
                        souscripteur = (covered.party
                            == covered.contract.subscriber)
                        if has_subscriber and souscripteur:
                            position = '01'
                        elif not has_subscriber and not serialized_members:
                            position = '03'
                        else:
                            position = '02'

                        party_address = covered.party.address_get()
                        if party_address:
                            idx = 0
                            line4 = party_address.address_lines.get('4_ligne4')
                            if not line4:
                                for idx in (3, 2, 5):
                                    line4 = party_address.address_lines.get(
                                        '{}_ligne{}'.format(idx, idx))
                                    if line4:
                                        break

                            party_address = E.ADRESSE_MEMBRE(
                                E.ADRESSE_AGREGEE(
                                    E.LIGNE1('{} {}'.format(
                                            party_address.party.first_name,
                                            party_address.party.name)),
                                    E.LIGNE2(party_address.address_lines.get(
                                        '2_ligne2') if idx != 2 else ''),
                                    E.LIGNE3(party_address.address_lines.get(
                                        '3_ligne3') if idx != 3 else ''),
                                    E.LIGNE4(line4),
                                    E.LIGNE5(party_address.address_lines.get(
                                        '5_ligne5', '') if idx != 5 else ''),
                                    E.LIGNE6('{} {}'.format(
                                            party_address.zip,
                                            party_address.city)),
                                    E.LIGNE7(party_address.address_lines.get(
                                            '7_ligne7'))
                                ))
                        else:
                            party_address = None

                        joignabilites = []
                        if covered.party.almerys_joignabilite_adresse_media:
                            joignabilites.append(E.JOIGNABILITE(
                                    E.MEDIA(covered.party
                                        .almerys_joignabilite_media),
                                    E.ADRESSE_MEDIA(covered.party.email),
                                    E.ACTIF('true')
                                    ))

                        membre = E.MEMBRE_CONTRAT(
                            E.SOUSCRIPTEUR('true' if souscripteur else 'false'),
                            E.POSITION(position),
                            E.TYPE_REGIME('RC'),
                            E.DATE_ENTREE(covered.start_date.isoformat()),
                            E.INDIVIDU(
                                E.REF_INTERNE_OS(covered.party.code),
                                E.DATE_NAISSANCE(
                                    covered.party.birth_date.isoformat()),
                                E.RANG_NAISSANCE(covered.party.birth_order),
                                # COMMUNE_NAISSANCE
                                E.NOM_PATRONIMIQUE(covered.party.birth_name
                                    or covered.party.name),
                                E.NOM_USAGE(covered.party.name),
                                E.PRENOM(covered.party.first_name),
                                E.CODE_SEXE(
                                    'MA'
                                    if covered.party.gender == 'male'
                                    else 'FE'),
                                E.PORTEUR_RISQUE(
                                    contract.dist_network.name
                                    if contract.dist_network
                                    else '')
                                # PROFESSION
                                # MEDECIN_TRAITANT
                                # IDENTITE_WEB
                                # AUTRE
                                # REF_INTERNE_ALMERYS
                                # DATE_CAL
                                # TYPE_CAL
                                ),
                            party_address,
                            E.MEDIA_ENVOI(
                                E.RELEVE_PRESTA(
                                    covered.party.almerys_releve_presta),
                                E.COURRIER_GESTION(
                                    covered.party.almerys_courrier_gestion),
                                ),
                            *joignabilites,
                            # NUM_ADHESION
                            E.AUTONOME(
                                'true' if config.autonomous else 'false'),
                            # MODE_PAIEMENT
                            E.NNI(covered.party.ssn_no_key[:13] if
                                covered.party.ssn_no_key else
                                covered.party.main_insured_ssn[:13] if
                                covered.party.main_insured_ssn else ''),
                            E.NNI_RATT(
                                covered.party.main_insured_ssn[:13]
                                if covered.party.main_insured_ssn and not
                                covered.party.ssn_no_key else ''),
                            )
                        membre.extend([
                                E.VIP('false'),
                                # DATE_CERTIFICATION_NNI
                                # DATE_CERTIFICATION_NNI_RATT
                                # DATE_DEBUT_SUSPENSION
                                # DATE_FIN_SUSPENSION
                                ])
                        if (contract.termination_reason ==
                                'unpaid_premium_termination'):
                            membre.extend([
                                    E.DATE_RADIATION(
                                        contract.final_end_date.isoformat()),
                                    E.MOTIF_RADIATION(
                                        'unpaid_premium_termination'),
                                    ])
                        members.append(membre)

                        if not souscripteur:
                            rattachements.append(E.RATTACHEMENT(
                                    E.REF_OS_RATTACHANT(
                                        contract.subscriber.code),
                                    E.REF_OS_RATTACHE(covered.party.code),
                                    E.LIEN_JURIDIQUE(
                                        liens.get(relation.type.code, 'AA')
                                        if relation else 'AA')
                                    ))
                        serialized_members.add(covered.party)

                    beneficiaire = E.BENEFICIAIRE(
                        E.REF_INTERNE_OS(covered.party.code),
                        E.TYPE_BENEF(
                            'AS' if (covered.party ==
                                contract.subscriber) else
                            liens.get(relation.type.code, 'AA') if relation
                            else 'AA'),
                        )
                    health_complement = None
                    if covered.party.main_health_complement:
                        health_complement = covered.party.main_health_complement
                        ro = E.RO()
                        if health_complement.hc_system:
                            ro.append(E.CODE_GRAND_REGIME(
                                    health_complement.hc_system.code
                                    ))
                        fund_number = (health_complement.insurance_fund_number
                            if health_complement.insurance_fund_number
                            else '000000000')
                        ro.extend(filter(lambda e: not empty_element(e), [
                                    E.CODE_CAISSE_RO(fund_number[2:5]),
                                    E.CENTRE_SS(fund_number[5:9]),
                                    ]))
                        beneficiaire.append(ro)

                    all_periods = [tpp for option in covered.options
                        for tpp in option.third_party_periods]
                    all_periods.sort(key=attrgetter('start_date'))
                    for option in covered.options:
                        for tp_period in option2periods.get(option, []):
                            extra_details = tp_period.extra_details
                            produit = E.PRODUIT(
                                E.REFERENCE_PRODUIT(extra_details[
                                        tp_prefix + 'reference_produit']),
                                E.DATE_ENTREE_PRODUIT(
                                    tp_period.start_date.isoformat())
                                )
                            if tp_period.end_date:
                                produit.append(E.DATE_SORTIE_PRODUIT(
                                        tp_period.end_date.isoformat()))
                            beneficiaire.append(produit)

                    noemise = (covered.item_desc.is_noemie
                            and health_complement
                            and health_complement.hc_system
                            and health_complement.insurance_fund_number)
                    beneficiaire.append(E.STATUT_NOEMISATION(
                            E.NOEMISE('true' if noemise else 'false'),
                            E.DATE_DEBUT_NOEMISATION(
                                covered.noemie_start_date.isoformat()
                                if covered.noemie_start_date else ''),
                            E.DATE_FIN_NOEMISATION(
                                covered.noemie_end_date.isoformat()
                                if covered.noemie_end_date else ''),
                            ))
                    if any(tpp.protocol.almerys_support_tp
                            for tpp in all_periods):
                        first_period = next(tpp
                            for tpp in all_periods
                            if tpp.protocol.almerys_support_tp)
                        bank_account = covered.party.claim_bank_account
                        bank = None
                        if bank_account:
                            bank_number = iban.compact(bank_account.number)
                            bank_code, bank_agency = bank_account.\
                                get_bank_identifiers_fr(bank_number)
                            bank = bank_account.bank
                        if bank:
                            service_tp = E.SERVICE_TP(
                                E.RIB(
                                    E.PRESTATION(
                                        E.TITULAIRE('{} {}'.format(
                                                covered.party.first_name,
                                                covered.party.name)[:80]),
                                        E.IBAN_PAYS(bank_number[:2]),
                                        E.IBAN_CONTROLE(bank_number[2:4]),
                                        E.IBAN_BBAN(bank_number[4:]),
                                        E.BIC_BANQUE(bank.bic[:4]),
                                        E.BIC_PAYS(bank.bic[4:6]),
                                        E.BIC_EMPLACEMENT(bank.bic[6:8]),
                                        E.BIC_BRANCHE(bank.bic[8:11]),
                                        E.NOM_BANQUE(bank.party.name[:100]),
                                        E.CODE_BANQUE(bank_code),
                                        E.AGENCE_BANQUE(bank_agency),
                                        E.NUM_COMPTE(bank_number[14:-2]),
                                        E.CLE_RIB(bank_number[-2:]),
                                        # DATE_EFFET
                                        )
                                    ),
                                E.DATE_DEBUT_VALIDITE(
                                    first_period.start_date.isoformat()),
                                E.ACTIVATION_DESACTIVATION('AC'),
                                E.ENVOI(
                                    first_period.extra_details.get(
                                        tp_prefix + 'service_tp_envoi',
                                        'AD'))
                                )
                    else:
                        first_period = all_periods[0]
                        service_tp = E.SERVICE_TP(
                            E.DATE_DEBUT_VALIDITE(
                                first_period.start_date.isoformat()),
                            E.ACTIVATION_DESACTIVATION('DE'),
                            E.ENVOI(first_period.extra_details.get(
                                    tp_prefix + 'service_tp_envoi', 'AD')),
                            )

                    services_tp_pec.append(
                        E.SERVICE_TP_PEC(beneficiaire, service_tp))

                contract_e.extend(members)
                contract_e.extend(rattachements)
                if services_tp_pec:
                    contract_e.append(E.SERVICE(*services_tp_pec))

                selected_period = None
                for period in periods:
                    if selected_period is None:
                        selected_period = period
                        continue
                    if period.start_date > selected_period.start_date:
                        selected_period = period
                    elif (period.start_date == selected_period.start_date
                            and selected_period.end_date is not None
                            and (period.end_date is None
                                or period.end_date > selected_period.end_date)):
                        selected_period = period

                extra_details = selected_period.extra_details
                contract_e.extend(filter(lambda e: not empty_element(e), [
                            E.REF_INTERNE_CG(
                                extra_details.get(
                                    tp_prefix + 'ref_interne', '')[:15]),
                            E.REF_COURTIER(
                                extra_details.get(
                                    tp_prefix + 'ref_courtier', '')[:15]),
                            E.REF_ENTREPRISE(
                                extra_details.get(
                                    tp_prefix + 'ref_entreprise', '')[:15]),
                            E.NUM_CONTRAT_COLLECTIF(
                                extra_details.get(
                                    tp_prefix + 'num_contrat_collectif',
                                    '')[:30]),
                            E.REF_SITE(
                                extra_details.get(
                                    tp_prefix + 'ref_site', '')[:15]),
                            E.REF_GESTIONNAIRE(
                                extra_details.get(
                                    tp_prefix + 'ref_gestionnaire', '')[:15]),
                            ]))

                perimetre_service.append(contract_e)

        filename = '{}.xml'.format(sequence)
        cls.write_batch_output(
            etree.tostring(
                document, encoding='UTF-8', pretty_print=True,
                xml_declaration=True),
            filename, root_dir=directory, **kwargs)

        TPPeriod.write(objects, {'status': 'sent'})


class AlmerysReturnBatch(batch.BatchRootNoSelect):
    'Return Almerys Batch'

    __name__ = 'batch.almerys.feedback'

    @classmethod
    def get_file_handler(cls):
        return return_almerys_hundler.AlmerysV3ReturnHandler()

    @classmethod
    def select_ids(cls, in_path, archive_path):
        files = cls.get_file_names_and_paths(in_path)
        if not files:
            cls.logger.info('No file found in directory %s' % in_path)
            return []
        all_elements = []
        for file_name, file_path in files:
            with open(file_path, 'rb') as _file:
                handler = cls.get_file_handler()
                all_elements.extend(handler.handle_file(_file))
        return all_elements

    @classmethod
    def execute(cls, objects, ids, in_path, archive_path):
        AlmerysReturn = Pool().get('return.almerys')
        Contract = Pool().get('contract')
        for sliced_element in grouped_slice(objects):
            vals = []
            for element in sliced_element:
                contract = Contract.search([
                    ('contract_number', '=', element[1])])[0].id
                almerys = AlmerysReturn.search([
                    ('file_number', '=', element[0]),
                    ('contract', '=', contract),
                    ('error_code', '=', element[2]),
                    ('error_label', '=', element[3])])
                if not almerys:
                    vals.append({
                        'file_number': element[0],
                        'contract': contract,
                        'error_code': element[2],
                        'error_label': element[3],
                        'status': 'to_treat', })
            AlmerysReturn.create(vals)
