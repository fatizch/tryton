from sql import Literal
from sql.operators import Mul

from trytond.modules.process import ClassAttr
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.cog_utils import model, fields
from trytond.pool import PoolMeta, Pool

__all__ = [
    'Endorsement',
    'EndorsementContract',
    'EndorsementPartUnion',
    ]


class Endorsement(CogProcessFramework):
    'Endorsement'

    __metaclass__ = ClassAttr
    __name__ = 'endorsement'

    endorsement_parts_union = fields.One2Many('endorsement.part.union',
        'endorsement', 'Endorsement Parts')
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

    @classmethod
    def __setup__(cls):
        super(EndorsementPartUnion, cls).__setup__()
        cls._buttons.update({
                'button_modify': {}
                })

    def get_contracts_name(self, name):
        return '\n'.join([x.rec_name for x in self.endorsement.contracts])

    @staticmethod
    def table_query():
        """ This object is only used to display endorsement part
        and launch the endorsement wizard in the right state
        according to the endorsement part. To insure a unique id
        we concatenate the part id and the endorsement id"""

        pool = Pool()
        endorsement = pool.get('endorsement').__table__()
        endorsement_part = pool.get('endorsement.part').__table__()
        endorsement_def_part_rel = pool.get(
            'endorsement.definition-endorsement.part').__table__()

        return endorsement_part.join(endorsement_def_part_rel, condition=(
                endorsement_def_part_rel.endorsement_part ==
                endorsement_part.id)
            ).join(endorsement, condition=(
                endorsement.definition == endorsement_def_part_rel.definition)
            ).select(
                (endorsement.id + Mul(10000000,
                        endorsement_part.id)).as_('id'),
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


class EndorsementContract:
    __metaclass__ = PoolMeta
    __name__ = 'endorsement.contract'

    @classmethod
    def __setup__(cls):
        super(EndorsementContract, cls).__setup__()
        cls._buttons.update({
                'button_modify': {},
                })

    @classmethod
    @model.CoopView.button_action('endorsement.act_resume_endorsement')
    def button_modify(cls, endorsements):
        pass
