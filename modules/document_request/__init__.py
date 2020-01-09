# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import batch
from . import document
from . import attachment
from . import report_engine
from . import party
from . import api


def register():
    Pool.register(
        document.DocumentDescription,
        document.DocumentRequest,
        document.DocumentRequestLine,
        batch.DocumentRequestBatch,
        document.DocumentReception,
        document.ReattachDocument,
        document.ReceiveDocumentLine,
        batch.BatchRemindDocuments,
        attachment.Attachment,
        module='document_request', type_='model')
    Pool.register(
        document.ExtraData,
        document.DocumentDescriptionExtraDataRelation,
        document.DocumentDescriptionOffered,
        document.DocumentRequestLineOffered,
        module='document_request', type_='model', depends=['offered'])
    Pool.register(
        document.ReceiveDocument,
        party.PartyReplace,
        module='document_request', type_='wizard')
    Pool.register(
        report_engine.ReportGenerate,
        module='document_request', type_='report')
    Pool.register(
        api.APIParty,
        module='document_request', type_='model', depends=['api', 'offered'])
    Pool.register(
        api.APIPartyWebConfiguration,
        document.DocumentDescriptionWebConfiguration,
        module='document_request', type_='model', depends=['web_configuration'])
    Pool.register(
        report_engine.ReportTemplateEmail,
        report_engine.ReportTemplatePaperFormRelation,
        module='document_request', type_='model',
        depends=['report_engine_email'])
