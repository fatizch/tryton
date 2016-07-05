from trytond.pool import PoolMeta

from trytond.modules.cog_utils import fields
from trytond.modules.report_engine import Printable

__metaclass__ = PoolMeta
__all__ = [
    'Dunning',
    'Level',
    ]


class Dunning(Printable):
    __name__ = 'account.dunning'

    current_attachment = fields.Function(
        fields.Many2One('ir.attachment', 'Current Report'),
        'get_current_attachment')

    def get_current_attachment(self, name):
        if not self.level.report_template:
            return None
        for attachment in self.attachments:
            if (attachment.document_desc ==
                    self.level.report_template.document_desc):
                return attachment.id

    def get_doc_template_kind(self):
        res = super(Dunning, self).get_doc_template_kind()
        res.append('dunning_letter')
        return res

    def get_contact(self):
        return self.party

    def get_sender(self):
        return self.company.party


class Level:
    __name__ = 'account.dunning.level'

    report_template = fields.Many2One('report.template', 'Report Template',
        domain=[('kind', '=', 'dunning_letter')],
        ondelete='RESTRICT')

    def process_report_template(self, dunnings):
        self.report_template.produce_reports(dunnings)

    def process_dunnings(self, dunnings):
        if self.report_template:
            self.process_report_template(dunnings)
        super(Level, self).process_dunnings(dunnings)

    @classmethod
    def _export_light(cls):
        return (super(Level, cls)._export_light() | set(['report_template']))
