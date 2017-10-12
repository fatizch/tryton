# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

import underwriting
import document
import batch
import party
import test_case


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
        test_case.TestCaseModel,
        module='underwriting', type_='model')

    Pool.register(
        underwriting.PlanUnderwriting,
        party.PartyReplace,
        module='underwriting', type_='wizard')
