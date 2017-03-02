# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

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
        cls.type_.selection.extend([
                ('underwriting_type', 'Underwriting Type'),
                ])


class RuleEngineRuntime:
    __metaclass__ = PoolMeta
    __name__ = 'rule_engine.runtime'

    @classmethod
    @check_args('claim')
    def _re_underwriting_non_received_documents(cls, args):
        claim = args['claim']
        non_received_documents = []
        underwritings = [x for x in claim.underwritings if x.state != 'state']
        for underwriting in underwritings:
            non_received_documents.extend([
                    (doc.document_desc.code, doc.rec_name)
                    for doc in underwriting.requested_documents
                    if doc.received is False
                    ])
        return non_received_documents
