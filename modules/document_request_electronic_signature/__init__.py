# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import attachment
import document
import report_engine
import contract
import claim


def register():
    Pool.register(
        attachment.Attachment,
        document.DocumentDescription,
        document.DocumentRequestLine,
        report_engine.ReportTemplate,
        module='document_request_electronic_signature', type_='model')
    Pool.register(
        contract.Contract,
        module='document_request_electronic_signature', type_='model',
        depends=['contract_insurance_document_request'])
    Pool.register(
        claim.Claim,
        module='document_request_electronic_signature', type_='model',
        depends=['claim_process'])
