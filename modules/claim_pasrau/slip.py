# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import datetime

from trytond.i18n import gettext
from trytond.pool import PoolMeta, Pool
from trytond.model import ModelView, Workflow
from trytond.model.exceptions import ValidationError
from trytond.pyson import Eval
from trytond.modules.coog_core import utils, coog_date

from . import dsn

__all__ = [
    'InvoiceSlipConfiguration',
    'Invoice',
    ]


class InvoiceSlipConfiguration(metaclass=PoolMeta):
    __name__ = 'account.invoice.slip.configuration'

    @classmethod
    def __setup__(cls):
        super(InvoiceSlipConfiguration, cls).__setup__()
        cls.slip_kind.selection.append(
            ('pasrau', 'Pasrau'))

    @classmethod
    def _event_code_from_slip_kind(cls, slip_kind):
        if slip_kind == 'pasrau':
            return 'pasrau_slips_generated'
        return super(InvoiceSlipConfiguration, cls)._event_code_from_slip_kind(
            slip_kind)


class Invoice(metaclass=PoolMeta):
    __name__ = 'account.invoice'

    @classmethod
    def __setup__(cls):
        super(Invoice, cls).__setup__()
        cls.business_kind.selection.append(('pasrau', 'Pasrau'))
        cls._buttons.update({
                'generate_dsn_message': {
                    'invisible': Eval('business_kind') != 'pasrau'
                    },
                })

    def _get_month_dsn_messages(self, _states):
        month_slips = self.search([
                ('business_kind', '=', 'pasrau'),
                ('invoice_date', '=', self.invoice_date)])
        if month_slips:
            messages = Pool().get('dsn.message').search([
                    ('state', 'in', _states),
                    ('origin', 'in', [str(x) for x in month_slips])]
                )
            return messages

    def _get_neorau_template(self):
        return dsn.NEORAUTemplate(self)

    @classmethod
    @ModelView.button_action('claim_pasrau.act_dsn_message')
    def generate_dsn_message(cls, slips):
        pool = Pool()
        DsnMessage = pool.get('dsn.message')
        if not DsnMessage.check_configuration():
            return
        dsn_messages = []
        for slip in slips:
            messages_not_done = slip._get_month_dsn_messages(
                ['draft', 'waiting'])
            if messages_not_done:
                raise ValidationError(gettext(
                        'claim_pasrau.msg_existing_messages_not_done'))
            message = slip._get_neorau_template().generate()
            dsnmessage = DsnMessage(type='out', state='waiting', origin=slip,
                message=message)
            dsn_messages.append(dsnmessage)
        if dsn_messages:
            DsnMessage.save(dsn_messages)
        # to_do wizard

    @classmethod
    @ModelView.button
    @Workflow.transition('posted')
    def post(cls, invoices):
        super(Invoice, cls).post(invoices)
        pasrau_invoices = [i for i in invoices if i.business_kind == 'pasrau']
        if pasrau_invoices:
            cls.generate_dsn_message(pasrau_invoices)

    def check_date_dsn_message_generation(self):
        max_date = datetime.date(self.invoice_date.year,
            self.invoice_date.month, 10)
        max_date = coog_date.add_month(max_date, 1)
        if utils.today() > max_date:
            raise ValidationError(gettext(
                    'claim_pasrau.msg_dsn_do_not_be_generated'))
