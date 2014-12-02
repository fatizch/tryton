from trytond.pool import PoolMeta

from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework

__metaclass__ = PoolMeta
__all__ = [
    'ContractSet',
    ]


class ContractSet(CogProcessFramework):
    __name__ = 'contract.set'
    __metaclass__ = ClassAttr
