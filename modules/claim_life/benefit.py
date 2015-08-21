from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = [
    'LossDescription',
    ]


class LossDescription:

    __name__ = 'benefit.loss.description'

    @classmethod
    def __setup__(cls):
        super(LossDescription, cls).__setup__()
        cls.loss_kind.selection.append(('life', 'Life'))
