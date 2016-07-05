# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

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
