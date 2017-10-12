# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import benefit
import wizard
import claim
import report_engine


def register():
    Pool.register(
        benefit.Benefit,
        benefit.DocumentRule,
        wizard.IndemnificationCalculationResult,
        claim.DocumentRequestLine,
        claim.Claim,
        claim.ClaimIndemnification,
        report_engine.ReportTemplate,
        module='claim_indemnification_document', type_='model')
    Pool.register(
        wizard.CreateIndemnification,
        module='claim_indemnification_document', type_='wizard')
