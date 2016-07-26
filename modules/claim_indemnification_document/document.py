from trytond.pool import PoolMeta
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Benefit',
    'DocumentRule',
    ]


class Benefit:
    __metaclass__ = PoolMeta
    __name__ = 'benefit'

    def calculate_required_docs_for_indemnification(self, args):
        if not self.documents_rules:
            return {}
        assert len(self.documents_rules) == 1
        rule = self.documents_rules[0]
        return rule.calculate_indemnification_doc_rule(args)


class DocumentRule(
        get_rule_mixin('indemnification_doc_rule',
            'Rule Engine for indemnifications',
            extra_string='Rule Extra Data')):
    __metaclass__ = PoolMeta
    __name__ = 'document.rule'
