#-*- coding:utf-8 -*-
from trytond.model import ModelView, ModelSQL

from trytond.modules.cog_utils import coop_string

__all__ = [
    'Payment',
    ]


class Payment(ModelSQL, ModelView):
    __name__ = 'account.payment'

    def get_icon(self, name=None):
        return 'payment'

    def get_rec_name(self, name):
        if self.date:
            return '%s - %s - [%s]' % (
                coop_string.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                coop_string.translate_value(self, 'state'))
        else:
            return '%s - [%s]' % (
                coop_string.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                coop_string.translate_value(self, 'state'))

    def get_synthesis_rec_name(self, name):
        if self.date:
            return '%s - %s - %s - [%s]' % (self.journal.rec_name,
                coop_string.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                coop_string.translate_value(self, 'state'))
        else:
            return '%s - %s - [%s]' % (
                coop_string.date_as_string(self.date),
                self.currency.amount_as_string(self.amount),
                coop_string.translate_value(self, 'state'))
