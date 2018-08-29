# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import ir
import batch
import rule_engine
import event
import linter
from trytond.pool import Pool
from rule_engine import get_rule_mixin, check_args, RuleTools

__all__ = [
    'get_rule_mixin',
    'check_args',
    'RuleTools',
    ]


def register():
    Pool.register(
        rule_engine.RuleTools,
        rule_engine.Context,
        rule_engine.RuleEngine,
        rule_engine.RuleEngineTable,
        rule_engine.RuleEngineRuleEngine,
        rule_engine.RuleParameter,
        rule_engine.RuleExecutionLog,
        rule_engine.TestCase,
        rule_engine.TestCaseValue,
        rule_engine.RuleFunction,
        rule_engine.ContextRuleFunction,
        rule_engine.RuleEngineFunctionRelation,
        rule_engine.RunTestsReport,
        rule_engine.RuleError,
        batch.ValidateRuleBatch,
        ir.View,
        event.EventTypeAction,
        linter.Linter,
        module='rule_engine', type_='model')
    Pool.register(
        rule_engine.RunTests,
        rule_engine.ValidateRuleTestCases,
        rule_engine.InitTestCaseFromExecutionLog,
        module='rule_engine', type_='wizard')
