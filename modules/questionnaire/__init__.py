# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool
import questionnaire
import extra_data
import rule_engine


def register():
    Pool.register(
        questionnaire.Questionnaire,
        questionnaire.ProductQuestionnaireRuleRelation,
        extra_data.QuestionnaireExtraDataRelation,
        extra_data.ExtraData,
        rule_engine.RuleEngine,
        module='questionnaire', type_='model')
