import copy

from trytond.pool import PoolMeta
from trytond.pyson import Eval, If

from trytond.modules.cog_utils import export


__metaclass__ = PoolMeta
__all__ = [
    'Sequence',
    'Property',
    ]


class Sequence:
    __name__ = 'ir.sequence'

    @classmethod
    def __setup__(cls):
        super(Sequence, cls).__setup__()
        cls.company = copy.copy(cls.company)
        cls.company.domain = export.clean_domain_for_import(
            cls.company.domain, 'company')


class Property:
    __name__ = 'ir.property'

    @classmethod
    def __setup__(cls):
        super(Property, cls).__setup__()
        cls.company = copy.copy(cls.company)
        cls.company.domain = [
            If(Eval('context', {}).contains('__importing__'),
                ('id', '>', 0),
                ('id', If(Eval('context', {}).contains('company'), '=', '!='),
                    Eval('context', {}).get('company', -1)))
            ]
