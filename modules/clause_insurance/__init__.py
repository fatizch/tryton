from trytond.pool import Pool
from .clause_rule import *
from .offered import *


def register():
    Pool.register(
        # From file clause_rule
        ClauseRule,
        RuleClauseRelation,
        # From file offered
        Offered,
        Product,
        OptionDescription,
        module='clause_insurance', type_='model')
