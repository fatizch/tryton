# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import Pool

from . import endorsement
from . import offered
from . import wizard
from . import configuration
from . import batch
from . import api


def register():
    Pool.register(
        batch.RecalculateEndorsementBatch,
        configuration.Configuration,
        endorsement.BillingInformation,
        endorsement.Contract,
        endorsement.Endorsement,
        endorsement.EndorsementBillingInformation,
        endorsement.EndorsementContract,
        offered.EndorsementBillingInformationField,
        offered.EndorsementDefinition,
        offered.EndorsementPart,
        offered.Product,
        wizard.BasicPreview,
        wizard.ChangeBillingInformation,
        wizard.ChangeContractExtraData,
        wizard.ChangeContractStartDate,
        wizard.ChangeContractSubscriber,
        wizard.ChangeDirectDebitAccount,
        wizard.ContractDisplayer,
        wizard.ManageExtraPremium,
        wizard.ManageOptions,
        wizard.ModifyCoveredElementInformation,
        wizard.NewCoveredElement,
        wizard.NewOptionOnCoveredElement,
        wizard.RecalculateAndReinvoiceContract,
        wizard.RemoveOption,
        wizard.TerminateContract,
        wizard.VoidContract,
        module='endorsement_insurance_invoice', type_='model')

    Pool.register(
        wizard.StartEndorsement,
        module='endorsement_insurance_invoice', type_='wizard')

    Pool.register(
        api.APIConfiguration,
        api.APIEndorsement,
        module='endorsement_insurance_invoice', type_='model', depends=['api'])

    Pool.register(
        api.APIClaimEndorsement,
        module='endorsement_insurance_invoice', type_='model',
        depends=['api', 'claim'])
