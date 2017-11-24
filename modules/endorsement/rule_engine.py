# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
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
    def build_endorsement_context(cls, endorsement_like, action=None):
        # endorsement_like is the bearer of the endorsement information.
        # It can be an endorsement, or an instance SelectEndorsement
        # or an instance of a class inheriting from EndorsementWizardStepMixin
        Endorsement = Pool().get('endorsement')
        context_ = {
            '_endorsement_effective_date': endorsement_like.effective_date,
            '_endorsement_signature_date': endorsement_like.signature_date,
            '_endorsement_definition': endorsement_like.definition if
            isinstance(endorsement_like, Endorsement)
            else endorsement_like.endorsement_definition,
            '_endorsement_action': action,
            }
        return context_


class RuleEngineRuntime:
    __name__ = 'rule_engine.runtime'

    @classmethod
    def _re_get_endorsement_in_progress(cls, args):
        return '_endorsement_effective_date' in args

    @classmethod
    def _re_get_endorsement_effective_date(cls, args):
        return args.get('_endorsement_effective_date', None)

    @classmethod
    def _re_get_endorsement_signature_date(cls, args):
        return args.get('_endorsement_signature_date', None)

    @classmethod
    def _re_get_endorsement_definition(cls, args):
        definition = args.get('_endorsement_definition', None)
        return definition.code if definition else None

    @classmethod
    def _re_get_endorsement_action(cls, args):
        return args.get('_endorsement_action', None)
