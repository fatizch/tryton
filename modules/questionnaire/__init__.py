# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import questionnaire
from . import extra_data
from . import rule_engine
from . import contract
from . import wizard
from . import api


def register():
    Pool.register(
        questionnaire.Questionnaire,
        questionnaire.QuestionnairePart,
        questionnaire.ProductQuestionnaireRuleRelation,
        questionnaire.QuestionnaireExtraDataRelation,
        extra_data.ExtraData,
        rule_engine.RuleEngine,
        wizard.RunQuestionnaireQuestions,
        wizard.RunQuestionnaireAnswers,
        wizard.RunQuestionnaireQuestionPart,
        wizard.RunQuestionnaireResult,
        wizard.RunQuestionnaireResultChoice,
        wizard.RunQuestionnaireProposition,
        module='questionnaire', type_='model')

    Pool.register(
        wizard.RunQuestionnaire,
        module='questionnaire', type_='wizard')

    Pool.register(
        contract.Contract,
        contract.ContractQuestionnaire,
        contract.ContractQuestionnaireAnswer,
        contract.ContractQuestionnaireResult,
        module='questionnaire', type_='model', depends=['contract'])

    Pool.register(
        wizard.ContractSubscribeFindProcess,
        module='questionnaire', type_='model', depends=['contract_process'])

    Pool.register(
        wizard.ContractProcessRunQuestionnaire,
        module='questionnaire', type_='wizard', depends=['contract_process'])

    Pool.register(
        wizard.ContractSubscribeQuestionnaire,
        module='questionnaire', type_='wizard', depends=['contract_process'])

    Pool.register(
        questionnaire.QuestionnaireDistribution,
        contract.ContractQuestionnaireResultDistribution,
        module='questionnaire', type_='model',
        depends=['contract_distribution'])

    Pool.register(
        wizard.RunDistributionQuestionnaire,
        module='questionnaire', type_='wizard', depends=['contract_process',
            'contract_distribution'])

    Pool.register(
        wizard.ContractSubscribeFindProcessDistribution,
        wizard.RunDistributionQuestionnaireQuestions,
        wizard.RunDistributionQuestionnaireResultChoice,
        module='questionnaire', type_='model', depends=['contract_process',
            'contract_distribution'])

    Pool.register(
        api.APICore,
        module='questionnaire', type_='model', depends=['api'])

    Pool.register(
        api.APIContract,
        module='questionnaire', type_='model', depends=['api', 'contract'])

    Pool.register(
        api.APICoreDistribution,
        module='questionnaire', type_='model', depends=['api', 'distribution'])

    Pool.register(
        api.APIContractDistribution,
        module='questionnaire', type_='model', depends=['api',
            'contract_distribution'])

    Pool.register(
        api.APICoreWebConfiguration,
        questionnaire.WebConfigurationQuestionnnairePart,
        module='questionnaire', type_='model', depends=['web_configuration'])
