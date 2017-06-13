# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.modules.coog_core import utils, model, fields
from trytond.pyson import Eval

__all__ = [
    'ContractNotification',
    ]


class ContractNotification(model.CoogSQL, model.CoogView):
    'Contract Notification'

    __name__ = 'contract.notification'

    name = fields.Char('Name', required=True, states={
            'readonly': Eval('treatment_date', False)
            }, depends=['treatment_date'])
    contract = fields.Many2One('contract', 'Contract', states={
            'readonly': Eval('treatment_date', False)
            }, required=True, ondelete='CASCADE', select=True,
            depends=['treatment_date'])
    subscriber = fields.Function(
        fields.Many2One('party.party', 'Subscriber'),
        'get_subscriber')
    planned_treatment_date = fields.Date('Planned Treatment Date',
        required=True, states={
            'readonly': Eval('treatment_date', False)
            }, depends=['treatment_date'])
    treatment_date = fields.Date('Treatment Date', readonly=True)

    @classmethod
    def __setup__(cls):
        super(ContractNotification, cls).__setup__()
        cls._buttons.update({
                'treat': {
                    'invisible': Eval('treatment_date', False),
                    'icon': 'check',
                    }
                })

    def get_subscriber(self, name):
        return self.contract.subscriber.id if (self.contract and
            self.contract.subscriber) else None

    def do_treat(self, date):
        self.treatment_date = date

    @classmethod
    @model.CoogView.button
    def treat(cls, notifications):
        for notification in notifications:
            notification.do_treat(utils.today())
        cls.save(notifications)
