from operator import itemgetter
from collections import defaultdict

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, Button
from trytond.pyson import Eval

from trytond.modules.cog_utils import model, fields
from trytond.modules.endorsement import EndorsementWizardPreviewMixin

__metaclass__ = PoolMeta
__all__ = [
    'StartEndorsement',
    'PreviewContractPremiums',
    'ContractPreview',
    'ContractPreviewPremium',
    ]


class PreviewContractPremiums(EndorsementWizardPreviewMixin,
        model.CoopView):
    'Preview Contract Premiums'

    __name__ = 'endorsement.start.preview_contract_premiums'

    contract_previews = fields.One2Many(
        'endorsement.start.preview_contract_premiums.contract', None,
        'Contracts', readonly=True)

    @classmethod
    def extract_endorsement_preview(cls, instance, endorsement=None):
        pool = Pool()
        Contract = pool.get('contract')
        Premium = pool.get('contract.premium')
        PremiumPreview = pool.get(
            'endorsement.start.preview_contract_premiums.premium')
        if not isinstance(instance, Contract):
            return {}
        premiums = []
        for premium in Premium.search([('main_contract', '=', instance.id),
                    ('start', '<=', endorsement.effective_date),
                    ['OR', ('end', '=', None),
                        ('end', '>=', endorsement.effective_date)]]):
            new_premium = {x: getattr(premium, x)
                for x in PremiumPreview.fields_to_extract()}
            new_premium['contract'] = instance.id
            if (hasattr(premium, 'option') and
                    premium.option):
                new_premium['option'] = premium.option.rec_name
            else:
                new_premium['option'] = None
            if (hasattr(premium.option, 'covered_element') and
                    premium.option.covered_element):
                new_premium['option_covered_element'] = \
                    premium.option.covered_element.rec_name
            else:
                new_premium['option_covered_element'] = None
            premiums.append(new_premium)

        sorted_premiums = sorted(premiums, key=itemgetter(
                'option_covered_element', 'option', 'start'))

        return {
            'id': instance.id,
            'currency_digits': instance.currency_digits,
            'currency_symbol': instance.currency_symbol,
            'premiums': sorted_premiums,
            }

    @classmethod
    def init_from_preview_values(cls, preview_values):
        contracts = defaultdict(lambda: {
                'contract': None,
                'currency_digits': 2,
                'currency_symbol': '',
                'old_contract_premiums': [],
                'new_contract_premiums': [],
                })
        for kind in ('old', 'new'):
            for key, value in preview_values[kind].iteritems():
                if not key.startswith('contract,'):
                    continue
                contract_preview = contracts[value['id']]
                contract_preview['currency_digits'] = \
                    value['currency_digits']
                contract_preview['currency_symbol'] = \
                    value['currency_symbol']
                contract_preview['contract'] = value['id']
                for elem in value['premiums']:
                    elem['currency_digits'] = value['currency_digits']
                    elem['currency_symbol'] = value['currency_symbol']
                    contract_preview['%s_contract_premiums' % kind].append(
                        elem)
        return {'contract_previews': contracts.values()}


class ContractPreview(model.CoopView):
    'Contract Preview'

    __name__ = 'endorsement.start.preview_contract_premiums.contract'

    contract = fields.Many2One('contract', 'Contract', readonly=True)
    currency_digits = fields.Integer('Currency Digits')
    currency_symbol = fields.Char('Currency Symbol')
    new_contract_premiums = fields.One2Many(
        'endorsement.start.preview_contract_premiums.premium', None,
        'New Contract Premiums', readonly=True)
    old_contract_premiums = fields.One2Many(
        'endorsement.start.preview_contract_premiums.premium', None,
        'Current Contract Premiums', readonly=True)


class ContractPreviewPremium(model.CoopView):
    'Premium Preview'

    __name__ = 'endorsement.start.preview_contract_premiums.premium'

    option = fields.Char('Option')
    option_covered_element = fields.Char('Covered Element for Option')
    start = fields.Date('Start')
    end = fields.Date('End')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    currency_digits = fields.Integer('Currency Digits')
    currency_symbol = fields.Char('Currency Symbol')

    @classmethod
    def fields_to_extract(cls):
        return ['contract', 'start', 'end', 'amount', 'option']


class StartEndorsement:
    __name__ = 'endorsement.start'

    preview_contract_premiums = StateView(
        'endorsement.start.preview_contract_premiums',
        'endorsement_premium.preview_contract_premiums_view_form', [
            Button('Summary', 'summary', 'tryton-go-previous', default=True),
            Button('Cancel', 'cancel', 'tryton-cancel'),
            Button('Apply', 'apply_endorsement', 'tryton-go-next'),
            ])

    def default_preview_contract_premiums(self, name):
        ContractPremiumsPreview = Pool().get(
            'endorsement.start.preview_contract_premiums')
        preview_values = self.endorsement.extract_preview_values(
            ContractPremiumsPreview.extract_endorsement_preview,
            endorsement=self.endorsement)
        return ContractPremiumsPreview.init_from_preview_values(preview_values)
