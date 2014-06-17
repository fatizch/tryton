from trytond.pool import PoolMeta

__metaclass__ = PoolMeta
__all__ = ['OptionDescription']


class OptionDescription:
    __name__ = 'offered.option.description'

    @classmethod
    def __setup__(cls):
        super(OptionDescription, cls).__setup__()
        cls.family.selection.append(('pc', 'Property & Casualty'))
