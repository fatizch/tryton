# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from operator import itemgetter
from collections import defaultdict
from itertools import groupby

from trytond.pool import PoolMeta, Pool
from trytond.wizard import StateView, Button
from trytond.pyson import Eval, Len

from trytond.modules.coog_core import model, fields
from trytond.modules.endorsement.wizard import EndorsementWizardPreviewMixin

from trytond.modules.premium.offered import PREMIUM_FREQUENCY

__all__ = [
    'StartEndorsement',
    'PreviewContractPremiums',
    'ContractPreview',
    'ContractPreviewPremium',
    ]


class PreviewContractPremiums(EndorsementWizardPreviewMixin,
        model.CoogView):
    'Preview Contract Premiums'

    __name__ = 'endorsement.start.preview_contract_premiums'

    contract_previews = fields.One2Many(
        'endorsement.start.preview_contract_premiums.contract', None,
        'Contracts', readonly=True)

    @classmethod
    def view_attributes(cls):
        return [
            ('/form/group[@id="one_contract"]', 'states',
                {'invisible': Len(Eval('contract_previews', [])) != 1}),
            ('/form/group[@id="multiple_contract"]', 'states',
                {'invisible': Len(Eval('contract_previews', [])) == 1}),
            ]

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
                ['OR', [('start', '>=', instance.start_date),
                        ('start', '<=', instance.final_end_date or
                            instance.end_date or
                            datetime.date.max)],
                    [('start', '<', instance.start_date),
                        ('end', '>=', endorsement.effective_date or
                            datetime.date.max)]]]):
            new_premium = {x: getattr(premium, x)
                for x in PremiumPreview.fields_to_extract()}
            new_premium['contract'] = instance.id
            new_premium['name'] = premium.full_name
            premiums.append(new_premium)

        sorted_premiums = sorted(premiums, key=itemgetter('name', 'start'))

        return {
            'id': instance.id,
            'currency_digits': instance.currency_digits,
            'currency_symbol': instance.currency_symbol,
            'premiums': sorted_premiums,
            }

    @classmethod
    def init_from_preview_values(cls, preview_values, endorsement=None):
        preview_values = cls.filter_preview_new_premiums(preview_values,
            endorsement)
        preview_values = cls.filter_preview_old_premiums(preview_values,
            endorsement)
        contracts = defaultdict(lambda: {
                'contract': None,
                'currency_digits': 2,
                'currency_symbol': '',
                'old_contract_premiums': [],
                'new_contract_premiums': [],
                })
        for kind in ('old', 'new'):
            for key, value in preview_values[kind].items():
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
        return {'contract_previews': list(contracts.values())}

    @classmethod
    def filter_preview_new_premiums(cls, preview_values, endorsement):
        if endorsement is None:
            return preview_values

        def keyfunc(premium):
            return (premium.get('contract', -1),
                premium.get('frequency', ''),
                premium.get('name', ''))

        new_preview_values = {}

        for key, preview in preview_values['new'].items():
            new_preview_values = preview.get('premiums', [])
            filtered_new_preview_values = []
            new_preview_values.sort(key=keyfunc)
            for _, premiums in groupby(new_preview_values, key=keyfunc):
                premiums_cpy = list(premiums)
                if len(premiums_cpy) == 1:
                    if (premiums_cpy[0].get('end', datetime.date.max) >
                            endorsement.effective_date):
                        filtered_new_preview_values.extend(premiums_cpy)
                    continue
                filtered_new_preview_values.extend([
                        p for p in premiums_cpy
                        if p.get('end', datetime.date.max) >
                        (endorsement.effective_date
                            or datetime.date.min)])
                preview_values['new'][key]['premiums'] = \
                    filtered_new_preview_values
        return preview_values

    @classmethod
    def filter_preview_old_premiums(cls, preview_values, endorsement):
        if endorsement is None:
            return preview_values
        old_preview_values = {}

        for key, preview in preview_values['old'].items():
            old_preview_values = preview.get('premiums', [])
            filtered_old_preview_values = [p for p in old_preview_values
                if p.get('start', datetime.date.min) <=
                    (endorsement.effective_date or datetime.date.max)]
            preview_values['old'][key]['premiums'] = \
                filtered_old_preview_values
        return preview_values


class ContractPreview(model.CoogView):
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


class ContractPreviewPremium(model.CoogView):
    'Premium Preview'

    __name__ = 'endorsement.start.preview_contract_premiums.premium'

    name = fields.Char('Name')
    start = fields.Date('Start')
    end = fields.Date('End')
    amount = fields.Numeric('Amount', digits=(16, Eval('currency_digits', 2)),
        depends=['currency_digits'])
    frequency = fields.Selection(PREMIUM_FREQUENCY, 'Frequency')
    currency_digits = fields.Integer('Currency Digits')
    currency_symbol = fields.Char('Currency Symbol')

    @classmethod
    def fields_to_extract(cls):
        return ['contract', 'start', 'end', 'amount', 'frequency']


class StartEndorsement(metaclass=PoolMeta):
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
        return ContractPremiumsPreview.init_from_preview_values(preview_values,
            endorsement=self.endorsement)
