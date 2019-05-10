# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.transaction import Transaction
from trytond.pool import Pool
from trytond.model import ModelSQL, ModelView, fields
from trytond.cache import Cache


class APIAccess(ModelSQL, ModelView):
    'API Access Right'

    __name__ = 'ir.api.access'

    group = fields.Many2One('res.group', 'Group', required=True,
        ondelete='CASCADE',
        help='Users from this group will be allowed to call business apis')
    api = fields.Char('API Name', required=True, help='The name of the api '
        'whose access will be allowed for the group')

    _access_cache = Cache('api_access_cache', context=False)

    @classmethod
    def create(cls, *args):
        result = super().create(*args)
        cls._access_cache.clear()
        return result

    @classmethod
    def write(cls, *args):
        super().write(*args)
        cls._access_cache.clear()

    @classmethod
    def delete(cls, *args):
        super().delete(*args)
        cls._access_cache.clear()

    @classmethod
    def check_access(cls, api_name):
        user = Transaction().user
        cached_value = cls._access_cache.get(user, -1)
        if cached_value != -1:
            return api_name in cached_value
        groups = Pool().get('res.user').get_groups()
        apis = {x.api for x in cls.search([('group', 'in', groups)])}
        cls._access_cache.set(user, apis)
        return api_name in apis
