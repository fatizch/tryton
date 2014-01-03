from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'User',
    ]


class User:
    __name__ = 'res.user'

    @classmethod
    def _export_skips(cls):
        result = super(User, cls)._export_skips()
        result.add('employee')
        return result

    @classmethod
    def _export_light(cls):
        result = super(User, cls)._export_light()
        result.add('main_company')
        result.add('company')
        return result
