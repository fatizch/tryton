from trytond.pool import PoolMeta

__metaclass__ = PoolMeta

__all__ = [
    'Line',
    ]


class Line:
    'Account Move Line'
    __name__ = 'account.move.line'

    def get_synthesis_rec_name(self, name):
        if self.origin:
            if (getattr(self.origin, 'get_synthesis_rec_name', None)
                    is not None):
                return self.origin.get_synthesis_rec_name(name)
            return self.origin.get_rec_name(name)
        return self.get_rec_name(name)
