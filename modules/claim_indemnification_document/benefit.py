# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.modules.rule_engine import get_rule_mixin

__all__ = [
    'Benefit',
    'DocumentRule',
    ]


class Benefit(metaclass=PoolMeta):
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
            extra_string='Rule Extra Data'), metaclass=PoolMeta):
    __name__ = 'document.rule'

    def get_rule_documentation_structure(self):
        doc = super(DocumentRule, self).get_rule_documentation_structure()
        if not self.indemnification_doc_rule:
            return doc
        doc.append(self.
            get_indemnification_doc_rule_rule_engine_documentation_structure())
        return doc
