# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.coog_core import fields
from trytond.modules.rule_engine import check_args

__all__ = [
    'RuleEngine',
    'RuleEngineRuntime',
    ]


class RuleEngine:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine'

    @classmethod
    def __setup__(cls):
        super(RuleEngine, cls).__setup__()
        cls.type_.selection.append(('doc_request', 'Document Request'))

    @fields.depends('type_')
    def on_change_with_result_type(self, name=None):
        if self.type_ == 'doc_request':
            return 'dict'
        return super(RuleEngine, self).on_change_with_result_type(name)


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('contract')
    def _re_documents_received(cls, args):
        return {
            x.document_desc.code: x.reception_date
            for x in args['contract'].document_request_lines
            if x.reception_date and x.document_desc
            }
