from sql import Literal
from sql.operators import Mul

from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.cog_utils import model, fields
from trytond.pool import Pool
from trytond.transaction import Transaction
from trytond.pyson import Eval

__all__ = [
    'Endorsement',
    'EndorsementPartUnion',
    ]


class Endorsement(CogProcessFramework):
    'Endorsement'

    __metaclass__ = ClassAttr
    __name__ = 'endorsement'

    endorsement_parts_union = fields.One2Many('endorsement.part.union',
        'endorsement', 'Endorsement Parts',
        context={'endorsement': [Eval('id')]},
        depends=['id'])
    created_attachments = fields.Function(
        fields.One2Many('ir.attachment', 'origin',
            'Created Attachments'), 'get_created_attachments')

    @classmethod
    def __setup__(cls):
        super(Endorsement, cls).__setup__()
        cls._buttons.update({
                'button_preview_changes': {}
                })

    @classmethod
    def _export_skips(cls):
        return (super(Endorsement, cls)._export_skips() |
            set(['endorsement_parts_union']))

    def get_created_attachments(self, name):
        pool = Pool()
        Attachment = pool.get('ir.attachment')
        return [x.id for x in Attachment.search([('origin', '=', '%s,%s'
                        % (self.__name__, self.id))])]

    @classmethod
    @model.CoopView.button_action(
        'endorsement_process.act_preview_changes')
    def button_preview_changes(cls, endorsements):
        pass

    def generate_and_attach_reports_in_endorsement(self, template_codes):
        for contract in self.contracts:
            contract.generate_and_attach_reports(template_codes, creator=self)


class EndorsementPartUnion(model.CoopSQL, model.CoopView):
    'Endorsement Part Display'

    __name__ = 'endorsement.part.union'

    name = fields.Char('Name')
    code = fields.Char('Code')
    endorsement = fields.Many2One('endorsement', 'Endorsement')
    contracts_name = fields.Function(
            fields.Char('Contracts Names'),
            'get_contracts_name')
    subscribers_name = fields.Function(
            fields.Char('Subscribers Names'),
            'get_subscribers_name')

    @classmethod
    def __setup__(cls):
        super(EndorsementPartUnion, cls).__setup__()
        cls._buttons.update({
                'button_modify': {}
                })

    def get_contracts_name(self, name):
        return '\n'.join([x.rec_name for x in self.endorsement.contracts])

    def get_subscribers_name(self, name):
        return self.endorsement.get_subscribers_name(None)

    @classmethod
    def table_query(cls):
        """ This object is only used to display endorsement part
        and launch the endorsement wizard in the right state
        according to the endorsement part. To insure a unique id
        we concatenate the part id and the endorsement id"""

        pool = Pool()
        ctx_endorsement = Transaction().context.get('endorsement', None)
        active_model = Transaction().context.get('active_model', None)

        endorsement = pool.get('endorsement').__table__()
        endorsement_part = pool.get('endorsement.part').__table__()
        endorsement_def_part_rel = pool.get(
            'endorsement.definition-endorsement.part').__table__()

        good_endorsements = None
        active_ids = Transaction().context.get('active_ids')
        if active_model == 'endorsement.part.union':
            good_endorsements = [x / 100000 for x in active_ids]
        elif ctx_endorsement:
            good_endorsements = ctx_endorsement
        elif active_model == 'endorsement':
            good_endorsements = active_ids
        if good_endorsements:
            join_condition = ((endorsement.state == 'draft') &
                endorsement.id.in_(good_endorsements))
        else:
            join_condition = (endorsement.state == 'draft')

        return endorsement_part.join(endorsement_def_part_rel, condition=(
                endorsement_def_part_rel.endorsement_part ==
                endorsement_part.id)
            ).join(endorsement, condition=(
                (endorsement.definition == endorsement_def_part_rel.definition)
                & join_condition)
            ).select(
                (endorsement_part.id + Mul(100000,
                        endorsement.id)).as_('id'),
                Literal(0).as_('create_uid'),
                Literal(0).as_('create_date'),
                Literal(0).as_('write_uid'),
                Literal(0).as_('write_date'),
                endorsement_part.name.as_('name'),
                endorsement_part.code.as_('code'),
                endorsement.id.as_('endorsement'))

    @classmethod
    @model.CoopView.button_action(
        'endorsement.act_start_endorsement')
    def button_modify(cls, endorsement_part_unions):
        pass
