import copy
from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'DocumentRequestLine',
    'DocumentRequest',
    'DocumentReceiveRequest',
    'DocumentTemplate',
    ]


class DocumentRequest:
    __name__ = 'document.request'

    @classmethod
    def __setup__(cls):
        super(DocumentRequest, cls).__setup__()
        cls.needed_by = copy.copy(cls.needed_by)
        cls.needed_by.selection.append(
            ('contract', 'Contract'))


class DocumentRequestLine:
    __name__ = 'document.request.line'

    @classmethod
    def __setup__(cls):
        super(DocumentRequestLine, cls).__setup__()
        cls.for_object = copy.copy(cls.for_object)
        cls.for_object.selection.append(
            ('contract', 'Contract'))
        cls.for_object.selection.append(
            ('contract.option', 'Option'))
        cls.for_object.selection.append(
            ('contract.covered_element', 'Covered Element'))
        cls.for_object.selection = list(set(cls.for_object.selection))


class DocumentReceiveRequest:
    __name__ = 'document.receive.request'

    @classmethod
    def allowed_values(cls):
        result = super(DocumentReceiveRequest, cls).allowed_values()
        result.update({'contract': ('Contract', 'contract_number')})
        return result


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
