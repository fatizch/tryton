from trytond.pool import PoolMeta, Pool
from trytond.modules.process_cog import CogProcessFramework
from trytond.modules.process import ClassAttr
from trytond.modules.cog_utils import fields
from trytond.pyson import Eval
from trytond.transaction import Transaction

__metaclass__ = PoolMeta
__all__ = [
    'EndorsementPartUnion',
    'EndorsementSet',
    ]


class EndorsementSet(CogProcessFramework):

    __name__ = 'endorsement.set'
    __metaclass__ = ClassAttr

    endorsements_summary = fields.Function(
        fields.Text('Endorsements Summary'),
        'get_endorsements_summary')
    endorsements_parts_union = fields.Function(
        fields.One2Many('endorsement.part.union',
            None, 'Endorsement Parts',
            context={'endorsement_set': Eval('id')},
            depends=['id']),
        'get_endorsements_parts_union', setter='setter_void')
    created_attachments = fields.Function(
        fields.One2Many('ir.attachment', 'origin',
            'Created Attachments'), 'get_created_attachments')
    attachments = fields.Function(
        fields.One2Many('ir.attachment', 'resource',
            'Attachments'), 'get_attachments')

    @classmethod
    def __setup__(cls):
        super(EndorsementSet, cls).__setup__()
        cls._error_messages.update({
                'no_effective_date': 'Effective date is not defined',
                })

    def check_endorsements_effective_date(self):
        if not self.effective_date:
            self.append_functional_error('no_effective_date')

    def get_endorsements_summary(self, name):
        res = ''
        for endorsement in self.endorsements:
            res += ', '.join(
                [x.contract_number + ', ' + x.subscriber.full_name
                    for x in endorsement.contracts])
            res += ':\n' + endorsement.endorsement_summary + '\n'
        return res

    def get_endorsements_parts_union(self, name):
        # See table_query method on EndorsementPartUnion
        # in endorsement_process/endorsement.py
        res = []
        for endorsement in self.endorsements:
            for part in endorsement.definition.endorsement_parts:
                res.append(part.id + 100000 * endorsement.id)
        return res

    def generate_and_attach_reports_on_contracts(self, template_codes):
        for endorsement in self.endorsements:
            for contract in endorsement.contracts:
                contract.generate_and_attach_reports(template_codes,
                    creator=endorsement)

    def generate_and_attach_reports_on_contract_set(self, template_codes):
        first_contract = self.endorsements[0].contracts[0]
        if not first_contract.contract_set:
            return
        first_contract.contract_set.generate_and_attach_reports_on_set(
            template_codes, creator=self)

    def get_created_attachments(self, name):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        operand = ['%s,%s' % (endorsement.__name__, endorsement.id)
            for endorsement in self.endorsements]
        operand.append('%s,%s' % (self.__name__, self.id))

        return [x.id for x in Attachment.search(
                [('origin', 'in', operand)])]

    def get_attachments(self, name):
        pool = Pool()
        Attachment = pool.get('ir.attachment')

        operand = ['%s,%s' % (endorsement.__name__, endorsement.id)
            for endorsement in self.endorsements]
        operand.append('%s,%s' % (self.__name__, self.id))

        return [x.id for x in Attachment.search(
                [('resource', 'in', operand)])]


class EndorsementPartUnion:
    __name__ = 'endorsement.part.union'

    @classmethod
    def table_query(cls):
        pool = Pool()
        EndorsementSet = pool.get('endorsement.set')
        ctx_endorsement_set = Transaction().context.get('endorsement_set',
            None)
        if ctx_endorsement_set:
            good_set = EndorsementSet(ctx_endorsement_set)
            good_endorsements = [x.id for x in good_set.endorsements]
            with Transaction().set_context({'endorsement': good_endorsements}):
                return super(EndorsementPartUnion, cls).table_query()
        else:
            return super(EndorsementPartUnion, cls).table_query()
