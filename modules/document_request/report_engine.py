# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.modules.coog_core import fields, model

__all__ = [
    'ReportGenerate',
    'ReportTemplateEmail',
    'ReportTemplatePaperFormRelation',
    ]


class ReportGenerate(metaclass=PoolMeta):
    __name__ = 'report.generate'

    @classmethod
    def get_context(cls, records, data):
        context = super(ReportGenerate, cls).get_context(records, data)
        context['force_remind'] = Transaction().context.get('force_remind',
            True)
        return context


class ReportTemplateEmail(metaclass=PoolMeta):
    __name__ = 'report.template'

    paper_form_descs = fields.One2Many('document.description', 'paper_form',
        'Paper Forms Descriptions', target_not_required=True)
    requested_paper_forms = fields.Many2Many(
        'report.template-paper_form', 'mail_template',
        'paper_form', 'Paper forms associated to request lines', states={
            'invisible': Eval('input_kind') != 'email'},
        domain=[('paper_form_descs', '!=', None)],
        help='Will dynamically attach empty paper form for the receiver to '
        'complete if he has a pending request line associated to this form')

    @classmethod
    def copy(cls, instances, default=None):
        default = default.copy() if default else {}
        default.setdefault('paper_form_descs', None)
        return super(ReportTemplateEmail, cls).copy(instances, default=default)

    @classmethod
    def _export_skips(cls):
        return super(ReportTemplateEmail, cls)._export_skips() | {
            'paper_form_descs'}

    def get_attachments(self, for_objects):
        res = super(ReportTemplateEmail, self).get_attachments(for_objects)
        paper_forms = set()
        for i, cur_object in enumerate(for_objects):
            cur_paper_forms = set()
            if hasattr(cur_object, 'get_request_lines'):
                for request_line in cur_object.get_request_lines():
                    if (request_line.received
                            or not request_line.document_desc.paper_form
                            or request_line.document_desc.paper_form not in
                            self.requested_paper_forms):
                        continue
                    cur_paper_forms.add(request_line.document_desc.paper_form)
            if i == 0:
                paper_forms = cur_paper_forms
            elif paper_forms != cur_paper_forms:
                # Incompatible objects not supported
                raise
        return res + list(paper_forms)


class ReportTemplatePaperFormRelation(model.CoogSQL, model.CoogView):
    'Report Template Paper Form Relation'

    __name__ = 'report.template-paper_form'

    mail_template = fields.Many2One('report.template', 'Mail Template',
        ondelete='CASCADE', required=True, select=True)
    paper_form = fields.Many2One('report.template', 'Paper Form',
        ondelete='RESTRICT', required=True, select=True)
