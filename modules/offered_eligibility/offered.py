from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields

__metaclass__ = PoolMeta
__all__ = [
    'OptionDescription',
    'OptionDescriptionRule',
]


class OptionDescription:
    __name__ = 'offered.option.description'

    eligibility_rule = fields.One2ManyDomain(
        'offered.option.description.rule', 'coverage', 'Eligibility Rule',
        domain=[('kind', '=', 'eligibility')], size=1)

    def check_eligibility(self, exec_context):
        if not self.eligibility_rule:
            return True
        return self.eligibility_rule[0].calculate(exec_context)


class OptionDescriptionRule:
    __name__ = 'offered.option.description.rule'

    @classmethod
    def __setup__(cls):
        super(OptionDescriptionRule, cls).__setup__()
        cls.kind.selection.append(('eligibility', 'Eligibility'))
