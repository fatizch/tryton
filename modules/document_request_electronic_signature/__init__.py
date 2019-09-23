# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
from . import attachment
from . import document
from . import report_engine
from . import contract
from . import claim
from . import signature
from . import extra_data


def register():
    Pool.register(
        attachment.Attachment,
        document.DocumentDescription,
        document.DocumentRequestLine,
        signature.Signature,
        report_engine.ReportTemplate,
        module='document_request_electronic_signature', type_='model')
    Pool.register(
        extra_data.ExtraData,
        document.OfferedDocumentDescription,
        signature.SignatureCredential,
        signature.SignatureConfiguration,
        signature.SignatureConfigurationExtraDataRelation,
        module='document_request_electronic_signature', type_='model',
        depends=['offered'])
    Pool.register(
        contract.Contract,
        module='document_request_electronic_signature', type_='model',
        depends=['contract_insurance_document_request'])
    Pool.register(
        claim.Claim,
        module='document_request_electronic_signature', type_='model',
        depends=['claim_process'])
