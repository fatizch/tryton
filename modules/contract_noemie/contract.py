# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.modules.coog_core import fields

__all__ = [
    'CoveredElement',
    ]

NOEMIE_CODE = [
    ('', ''),
    ('01', '[01] Birth date absent onMvt. of member'),
    ('02', '[02] Wrong registration number'),
    ('03', '[03] Wrong movement code'),
    ('04', '[04] C.O Wrong number'),
    ('05', '[05] Wrong type of contract'),
    ('06', '[06] Invalid start date of contract'),
    ('07', '[07] Invalid end date of contract'),
    ('08', '[08] Incomp. start date end date of contract'),
    ('09', '[09] Wrong beneficiary birth date'),
    ('10', '[10] Bad beneficiary rank'),
    ('11', '[11] Reserved to CPAM'),
    ('13', '[13] Reserved to CPAM'),
    ('14', '[14] Unknown Annul imposs Rub O.C./CT'),
    ('15', '[15] Beneficiary creation impossible> 19'),
    ('16', '[16] O.C creation impossible> 3'),
    ('17', '[17] O.C unknown to the file'),
    ('18', '[18] Insured unknown to the file'),
    ('19', '[19] Reserved to CPAM'),
    ('20', '[20] Beneficiary unknown to the file'),
    ('21', '[21] Insured managed by another Caisse'),
    ('22', '[22] Validity period O.C. not outstanding'),
    ('23', '[23] Not mutualist insured'),
    ('24', '[24] Not mutualist beneficiary'),
    ('25', '[25] Modif. imposs. Rub. O.C./CT not found'),
    ('26', '[26] Reserved to CPAM'),
    ('27', '[27] Divergence on Civil Status'),
    ('28', '[28] Rub. Benef. only allowed for VITALE'),
    ('29', '[29] Origin different flow of the option'),
    ('30', '[30] Matricular key absent or erroneous'),
    ('31', '[31] Birthday benef. diverge'),
    ('32', '[32] Modification info C.O. acquitted'),
    ('33', '[33] Creation info C.O. acquitted'),
    ('34', '[34] Cancellation info C.O. acquitted'),
    ('35', '[35] Refusal of the Member trades'),
    ('36', '[36] Member mutual status'),
    ('37', '[37] C.O. not founded'),
    ('38', '[38] Cash change XXX to XXX - with convention'),
    ('40', '[40] Matrix Id Change: XXXXX XX XXX XXX'),
    ('41', '[41] Change Birth Date. Benefit: XX/XX/XX'),
    ('43', '[43] Mutual Beneficiary Cancellation'),
    ]

ACQUITEMENT_CODES = ['32', '33', '34']
REPORTED_CODES = ['13', '19', '27', '38', '40', '41', '43']
REJECTED_CODES = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10',
    '11', '14', '15', '16', '17', '18', '20', '21', '22', '23', '24', '25',
    '26', '28', '29', '30', '31', '35']


class CoveredElement(metaclass=PoolMeta):
    __name__ = 'contract.covered_element'

    is_noemie = fields.Function(
        fields.Boolean('Is Noemie'),
        'getter_is_noemie')
    noemie_status = fields.Function(
        fields.Selection([
            ('', ''), ('waiting', 'Waiting'),
            ('acquitted', 'Acquitted'), ('rejected', 'Rejected'),
            ('reported', 'Reported')], 'Noemie Status',
            depends=['is_noemie']),
        'getter_noemie_status')
    noemie_status_string = noemie_status.translated('noemie_status')
    noemie_update_date = fields.Date('Noemie Update Date',
        states={'invisible': ~Eval('is_noemie') | ~Eval('noemie_update_date')},
        depends=['is_noemie'], readonly=True)
    noemie_return_code = fields.Selection(NOEMIE_CODE, 'Noemie Return Code',
        states={'invisible': ~Eval('is_noemie') | ~Eval('noemie_return_code')},
        depends=['is_noemie'], readonly=True)
    noemie_return_code_string = \
        noemie_return_code.translated('noemie_return_code')

    @classmethod
    def view_attributes(cls):
        return super(CoveredElement, cls).view_attributes() + [
            ("/form/group[@id='noemie_management']", 'states',
                {'invisible': ~Eval('is_noemie')}),
            ]

    def getter_is_noemie(self, name):
        return self.item_desc.is_noemie

    def getter_noemie_status(self, name):
        if not self.is_noemie:
            return ''
        elif not self.noemie_return_code:
            return 'waiting'
        elif self.noemie_return_code in ACQUITEMENT_CODES:
            return 'acquitted'
        elif self.noemie_return_code in REPORTED_CODES:
            return 'reported'
        elif self.noemie_return_code in REJECTED_CODES:
            return 'rejected'

    @staticmethod
    def default_noemie_return_code():
        return ''

    def recalculate(self):
        super().recalculate()
        if self.party and self.item_desc.is_noemie:
            CoveredElement = Pool().get('contract.covered_element')
            covered_elements = CoveredElement.search([
                    ('id', '!=', self.id),
                    ('item_desc.is_noemie', '=', True),
                    ('party', '=', self.party.id)])
            if covered_elements:
                self.noemie_return_code = covered_elements[0].noemie_return_code
                self.noemie_update_date = covered_elements[0].noemie_update_date
                self.noemie_status = covered_elements[0].noemie_status
            else:
                self.noemie_return_code = ''
                self.noemie_update_date = None
                self.noemie_status = 'waiting'

    @fields.depends('noemie_return_code', 'noemie_update_date', 'noemie_status')
    def on_change_party(self):
        super().on_change_party()

    @classmethod
    def update_noemie_status(cls, covered_elements, noemie_return_code,
            noemie_update_date):

        if not covered_elements:
            return

        cls.write(covered_elements, {
                'noemie_update_date': noemie_update_date,
                'noemie_return_code': noemie_return_code,
                })

        Event = Pool().get('event')
        description = "%s %s %s" % (covered_elements[0].party.full_name,
            covered_elements[0].noemie_return_code_string, noemie_update_date)
        if covered_elements[0].noemie_status == 'rejected':
            Event.notify_events(covered_elements,
                'noemie_rejet', description=description)
        elif covered_elements[0].noemie_status == 'reported':
            Event.notify_events(covered_elements,
                'noemie_signalements', description=description)
        elif covered_elements[0].noemie_status == 'acquitted':
            Event.notify_events(covered_elements,
                'noemie_acquitements', description=description)
