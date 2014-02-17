from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'DocumentTemplate',
    ]


class DocumentTemplate:
    __name__ = 'document.template'

    def get_possible_kinds(self):
        result = super(DocumentTemplate, self).get_possible_kinds()
        if not self.on_model:
            return result
        if not self.on_model.model == 'contract':
            return result
        result.append(('contract', 'Contract Documents'))
        return result
