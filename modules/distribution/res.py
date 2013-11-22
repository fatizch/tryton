from trytond.pool import PoolMeta

from trytond.modules.coop_utils import fields

__all__ = [
    'User',
    ]


class User():
    'User'

    __name__ = 'res.user'
    __metaclass__ = PoolMeta

    dist_network = fields.Many2One('distribution.dist_network',
        'Distribution Network')

    @classmethod
    def _export_skips(cls):
        result = super(User, cls)._export_skips()
        result.add('employee')
        result.add('salt')
        return result

    @classmethod
    def _export_light(cls):
        return set(['dist_network', 'main_company', 'company'])

    def _export_override_password(self, exported, result, my_key):
        return ''

    @classmethod
    def _import_override_password(cls, instance_key, good_instance,
            field_value, values, created, relink):
        if good_instance.id:
            # Do not try to override the password
            return
        # For new users, set the login as password in the new db
        good_instance.password = values['login']
        return
