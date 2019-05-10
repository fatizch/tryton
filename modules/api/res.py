# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.model import fields


class Group(metaclass=PoolMeta):
    __name__ = 'res.group'

    api_access = fields.One2Many('ir.api.access', 'group', 'APIs',
        help='The list of business apis this group will have access to')

    @classmethod
    def create(cls, *args):
        result = super().create(*args)
        Pool().get('ir.api.access')._access_cache.clear()
        return result

    @classmethod
    def write(cls, *args):
        super().write(*args)
        Pool().get('ir.api.access')._access_cache.clear()

    @classmethod
    def delete(cls, *args):
        super().delete(*args)
        Pool().get('ir.api.access')._access_cache.clear()


class UserGroup(metaclass=PoolMeta):
    __name__ = 'res.user-res.group'

    @classmethod
    def create(cls, *args):
        result = super().create(*args)
        Pool().get('ir.api.access')._access_cache.clear()
        return result

    @classmethod
    def write(cls, *args):
        super().write(*args)
        Pool().get('ir.api.access')._access_cache.clear()

    @classmethod
    def delete(cls, *args):
        super().delete(*args)
        Pool().get('ir.api.access')._access_cache.clear()
