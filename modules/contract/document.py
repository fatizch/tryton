import copy

from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'DocumentTemplate',
    ]


class DocumentTemplate:
    __name__ = 'document.template'

    @classmethod
    def __setup__(cls):
        super(DocumentTemplate, cls).__setup__()
        cls.kind = copy.copy(cls.kind)
        cls.kind.selection.append(('contract', 'Contract Documents'))
        cls.kind.selection = list(set(cls.kind.selection))
