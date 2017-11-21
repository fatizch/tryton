# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.coog_core import fields


__metaclass__ = PoolMeta
__all__ = [
    'RuleEngine',
    'RuleEngineRuntime',
    ]


class RuleEngine:
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('endorsement_start', 'Endorsement Start'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'endorsement_start':
            return 'boolean'
        return super(RuleEngine, self).on_change_with_result_type(name)

    @classmethod
    def build_endorsement_context(cls, endorsement, action=None):
        context_ = {
            '_endorsement_effective_date': endorsement.effective_date,
            '_endorsement_definition': endorsement.definition,
            '_endorsement_action': action,
            }
        return context_


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_get_endorsement_in_progess(cls, args):
        return '_endorsement_effective_date' in args

    @classmethod
    def _re_get_endorsement_effective_date(cls, args):
        return args.get('_endorsement_effective_date', None)

    @classmethod
    def _re_get_endorsement_definition(cls, args):
        definition = args.get('_endorsement_definition', None)
        return definition.code if definition else None

    @classmethod
    def _re_get_endorsement_action(cls, args):
        return args.get('_endorsement_action', None)
