from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta

__all__ = [
    'Clause',
    ]


class Clause:
    __name__ = 'clause'

    coverages = fields.Many2Many(
        'offered.option.description-beneficiary_clause', 'clause', 'coverage',
        'Coverages')

    @classmethod
    def __setup__(cls):
        super(Clause, cls).__setup__()
        cls.kind.selection += [('beneficiary', 'Beneficiary')]

    @classmethod
    def _export_skips(cls):
        res = super(Clause, cls)._export_skips()
        res.add('coverages')
        return res
