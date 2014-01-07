from trytond.pool import Pool
from .offered import *
from .benefit import *
from .benefit_rule import *
from .reserve_rule import *
from .business_rule import *


def register():
    Pool.register(
        # From offered
        OptionDescription,
        # From Benefit
        EventDescription,
        LossDescription,
        Benefit,
        InsuranceBenefit,
        LossDescriptionDocumentDescriptionRelation,
        EventDescriptionLossDescriptionRelation,
        BenefitLossDescriptionRelation,
        OptionDescriptionBenefitRelation,
        LossDescriptionExtraDataRelation,
        BenefitExtraDataRelation,
        # From Benefit Rule
        BenefitRule,
        BenefitRuleStage,
        # From Reserve Rule
        ReserveRule,
        #From Business Rule
        BusinessRuleRoot,
        module='benefit', type_='model')
