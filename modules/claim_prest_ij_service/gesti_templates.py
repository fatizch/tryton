# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from lxml import etree
from lxml.builder import ElementMaker
import os


class GestipTemplate(object):
    xsi = "http://www.w3.org/2001/XMLSchema-instance"
    schemaLocation = None
    schema_filename = None
    namespace = None

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
            encoding='utf8')

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
            self.M.IP(  # should there be an operation at this level ?
                self.M.Identite(data['code_ga']),
                self.M.Denomination(data['opedi_name'])
                ),
            Nature="GESTIP",
            Version="02.00",
        )

        for req in data['requests']:
            self.xml[3].append(self.M.Entreprise(
                self.M.Identite(req.subscription.siren),
                self.M.RaisonSociale(req.subscription.parties[0].name),
                Operation=req.operation.upper()
                ))
