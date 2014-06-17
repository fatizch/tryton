from trytond.pool import PoolMeta
from trytond.pyson import Eval

from trytond.modules.cog_utils import fields


__metaclass__ = PoolMeta
__all__ = [
    'Contract',
    ]

_STATES = {
    'readonly': Eval('status') != 'quote',
    }
_DEPENDS = ['status']


class Contract:
    __name__ = 'contract'

    manual_billing = fields.Boolean('Manual Billing', states=_STATES,
        depends=_DEPENDS)
