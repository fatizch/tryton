# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import underwriting
import document
import batch


def register():
    Pool.register(
        document.DocumentRequestLine,
        underwriting.UnderwritingDecisionType,
        underwriting.UnderwritingType,
        underwriting.UnderwritingTypeDecision,
        underwriting.UnderwritingTypeDocumentRule,
        underwriting.Underwriting,
        underwriting.UnderwritingResult,
        underwriting.PlanUnderwritingDate,
        batch.UnderwritingActivationBatch,
        module='underwriting', type_='model')

    Pool.register(
        underwriting.PlanUnderwriting,
        module='underwriting', type_='wizard')
