from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'Model',
    ]


class Model:
    '''
        We need to override the Model Class in order to add the is_workflow
        field so we can find which classes are workflow compatible.
    '''

    __name__ = 'ir.model'

    is_workflow = fields.Boolean('Is Workflow')
