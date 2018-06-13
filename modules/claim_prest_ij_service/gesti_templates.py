# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import os

from lxml import etree
from lxml.builder import ElementMaker
from itertools import groupby

from trytond.pool import Pool


class GestipTemplate(object):
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    schemaLocation = None
    schema_filename = None
    namespace = None
    encoding = 'iso-8859-1'

    def __init__(self, data):
        self.M = ElementMaker(
                    namespace=self.namespace,
                    nsmap={None: self.namespace, 'xsi': self.xsi},
                )
        schema_filepath = os.path.join(os.path.dirname(__file__), 'resources/'
            + self.schema_filename)
        with open(schema_filepath, 'r') as f:
            schema = etree.XMLSchema(etree.XML(f.read()))
            self.parser = etree.XMLParser(schema=schema)
        self.generate(data)
        self.xml.attrib[etree.QName(self.xsi, 'schemaLocation')] = \
            self.schemaLocation
        self.validate()

    def generate(self, data):
        raise NotImplementedError

    def __str__(self):
        return etree.tostring(self.xml,
            pretty_print=True,
            xml_declaration=True,
            encoding=self.encoding)

    def validate(self):
        return etree.fromstring(str(self), self.parser)


class GestipHeader(GestipTemplate):
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    schemaLocation = "urn:cnamts:tlsemp:ENTGESTIP ROOT_ENTGESTIP_V02_00.xsd"
    schema_filename = 'ROOT_ENTGESTIP_V02_00.xsd'
    namespace = "urn:cnamts:tlsemp:ENTGESTIP"

    def generate(self, data):
        self.xml = self.M.Entete(
            self.M.Identification(data['gesti_header_identification']),
            self.M.Temps(data['timestamp']),
            self.M.Fonction("9"),
            self.M.Info(data['access_key']),
            self.M.Emetteur(
                self.M.Identite(data['siret_opedi'], R="SIRET"),
                self.M.Qualite("OPEDI")
                ),
            self.M.Recepteur(
                self.M.Identite("010000000", R="ORGIR"),
                self.M.Qualite("ACNAM")
                ),
            self.M.Document(
                self.M.Mindex(
                    self.M.Profil("GESTIP"),
                    self.M.Identification(
                        data['gesti_document_identification']),
                    self.M.Temps(data['timestamp']),
                    self.M.Fonction("9"),
                ),
                self.M.Lien(
                    self.M.Adresse(data['gesti_document_filename']),
                    self.M.Type("XML"),
                ),
            ),
            PGMD_Profil="ENTGESTIP",
            Profil_Version="02.00",
        )


class GestipDocument(GestipTemplate):
    schemaLocation = "urn:.cnamts:tlsemp:GESTIP ROOT_GESTIP_V02_00.xsd"
    schema_filename = 'ROOT_GESTIP_V02_01.xsd'
    namespace = "urn:.cnamts:tlsemp:GESTIP"

    def generate(self, data):
        self.xml = self.M.GESTIP(
            self.M.Identification(data['gesti_document_identification']),
            self.M.Temps(data['timestamp']),
            self.M.Fonction("9"),
            self.M.IP(
                self.M.Identite(data['code_ga']),
                self.M.Denomination(data['opedi_name'])
                ),
            Nature="GESTIP",
            Version="02.00",
        )

        def keyfunc(x):
            return x.subscription.siren

        reqs = sorted(data['requests'], key=keyfunc)

        for siren, requests in groupby(reqs, key=keyfunc):
            requests = list(requests)
            company_requests, person_requests = [], []
            [person_requests.append(x) if x.subscription.ssn
                else company_requests.append(x) for x in requests]
            for company_request in company_requests:
                to_append = self.M.Entreprise(
                    self.M.Identite(siren),
                    self.M.RaisonSociale(
                        company_request.subscription.parties[0].name),
                    Operation=company_request.operation.upper()
                )
                self.xml[3].append(to_append)
            if person_requests:
                company = Pool().get('party.party').search(
                        [('siren', '=', siren)])[0]
                to_append = self.M.Entreprise(
                    self.M.Identite(siren),
                    self.M.RaisonSociale(company.name),
                    *[self.person_element(r) for r in person_requests]
                    )
                self.xml[3].append(to_append)

    def person_element(self, request):
        data = [
            self.M.NIR(request.subscription.ssn[:-2]),
            self.M.Nom(request.subscription.parties[0].name),
            self.M.Prenom(request.subscription.parties[0].first_name),
        ]
        if request.operation == 'cre':
            if request.period_end:
                data.append(self.M.Prevoyance(
                    self.M.DateDebut(request.period_start.isoformat()),
                    self.M.DateFin(request.period_end.isoformat()),
                    self.M.DateDebutRetro(request.retro_date.isoformat()),
                    self.M.TypePE('IJ'),
                    IdCouverture=request.period_identification,
                    Operation=request.operation.upper()
                    ))
            else:
                data.append(self.M.Prevoyance(
                    self.M.DateDebut(request.period_start.isoformat()),
                    self.M.DateDebutRetro(request.retro_date.isoformat()),
                    self.M.TypePE('IJ'),
                    IdCouverture=request.period_identification,
                    Operation=request.operation.upper()
                    ))
        return self.M.Salarie(*data, Operation=request.operation.upper())
