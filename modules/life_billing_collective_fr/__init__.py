from trytond.pool import Pool

from .offered import *
from .contract import *
from .billing import *
from .rule_engine import *
from .party import *
from .company import *
from .account import *
from .collection import *

from trytond.modules.coop_utils import expand_tree
PremiumRateLineTreeExpansion = expand_tree('contract.premium_rate.line')
RateNoteLineTreeExpansion = expand_tree('billing.premium_rate.form.line')


def register():
    Pool.register(
        # from Product
        Product,
        OptionDescription,
        PremiumRateRule,
        FareClass,
        FareClassGroup,
        FareClassGroupFareClassRelation,
        PremiumRateRuleLine,
        #from Contract
        Contract,
        CoveredData,
        # from billing,
        PremiumRateLine,
        RateNote,
        RateNoteLine,
        BillingPremiumRateFormCreateParam,
        BillingPremiumRateFormCreateParamClient,
        BillingPremiumRateFormCreateParamProduct,
        BillingPremiumRateFormCreateParamContract,
        BillingPremiumRateFormCreateParamGroupClient,
        BillingPremiumRateFormCreateShowForms,
        BillingPremiumRateFormReceiveSelect,
        BillingPremiumRateFormReceiveCreateMove,
        # From account
        Move,
        MoveLine,
        # from Rule Engine
        RuleEngineRuntime,
        # from Party
        GroupParty,
        Party,
        # For tree expand
        PremiumRateLineTreeExpansion,
        RateNoteLineTreeExpansion,
        # from Company
        Company,
        module='life_billing_collective_fr', type_='model')
    Pool.register(
        BillingPremiumRateFormCreate,
        BillingPremiumRateFormReceive,
        # From collection
        CollectionCreate,
        module='life_billing_collective_fr', type_='wizard')
