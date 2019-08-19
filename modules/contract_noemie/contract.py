# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

from datetime import date
from dateutil.relativedelta import relativedelta

from sql import Literal, Null
from sql.aggregate import Max, Min
from sql.conditionals import Coalesce, Greatest, NullIf

from trytond import backend
from trytond.pool import PoolMeta, Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

from trytond.modules.coog_core import fields

__all__ = [
    'Contract',
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


class Contract(metaclass=PoolMeta):
    __name__ = 'contract'

    def compute_noemie_dates(self, caller=None):
        for covered_element in self._get_calculate_targets(
                'covered_elements'):
            covered_element.update_noemie_dates()
        self.save()


class CoveredElement(metaclass=PoolMeta):
    __name__ = 'contract.covered_element'

    is_noemie = fields.Function(
        fields.Boolean('Is Noemie'),
        'on_change_with_is_noemie')
    noemie_status = fields.Function(
        fields.Selection([
            ('', ''), ('waiting', 'Waiting'),
            ('acquitted', 'Acquitted'), ('rejected', 'Rejected'),
            ('reported', 'Reported')], 'Noemie Status',
            depends=['is_noemie']),
        'on_change_with_noemie_status')
    noemie_status_string = noemie_status.translated('noemie_status')
    noemie_update_date = fields.Date('Noemie Update Date',
        states={'invisible': ~Eval('is_noemie') | ~Eval('noemie_update_date')},
        depends=['is_noemie'], readonly=True)
    noemie_return_code = fields.Selection(NOEMIE_CODE, 'Noemie Return Code',
        states={'invisible': ~Eval('is_noemie') | ~Eval('noemie_return_code')},
        depends=['is_noemie'], readonly=True)
    noemie_return_code_string = \
        noemie_return_code.translated('noemie_return_code')
    noemie_start_date = fields.Date('Noemie Start Date',
        states={'invisible': ~Eval('is_noemie') | ~Eval('noemie_start_date')},
        depends=['is_noemie'], readonly=True)
    noemie_end_date = fields.Date('Noemie End Date',
        states={'invisible': ~Eval('is_noemie') | ~Eval('noemie_end_date')},
        depends=['is_noemie'], readonly=True)

    @classmethod
    def view_attributes(cls):
        return super(CoveredElement, cls).view_attributes() + [
            ("/form/group[@id='noemie_management']", 'states',
                {'invisible': ~Eval('is_noemie')}),
            ]

    @classmethod
    def __register__(cls, module_name):
        pool = Pool()
        Option = pool.get('contract.option')
        Item = pool.get('offered.item.description')
        History = pool.get('contract.activation_history')
        TableHandler = backend.get('TableHandler')
        table_handler = TableHandler(cls)
        cursor = Transaction().connection.cursor()
        migrate_dates = not table_handler.column_exist('noemie_start_date')
        super().__register__(module_name)
        if migrate_dates:
            option = Option.__table__()
            item = Item.__table__()
            item2 = Item.__table__()
            history = History.__table__()
            covered = cls.__table__()
            q_table = history.join(covered,
                condition=history.contract == covered.contract).join(option,
                condition=option.covered_element == covered.id).join(item,
                condition=item.id == covered.item_desc).select(
                covered.party,
                Max(Coalesce(history.end_date, date.min)).as_(
                    'c_end_date'),
                Min(Coalesce(history.start_date, date.min)).as_(
                    'c_start_date'),
                Max(Coalesce(option.manual_end_date, date.min)).as_(
                    'o_m_end_date'),
                Max(Coalesce(option.automatic_end_date, date.min)).as_(
                    'o_a_end_date'),
                Min(Coalesce(option.manual_start_date, date.max)).as_(
                    'o_m_start_date'),
                where=(item.is_noemie == Literal(True)) &
                    (covered.party != Null),
                group_by=covered.party)
            covered_up = cls.__table__()
            cursor.execute(*covered_up.update(
                    columns=[covered_up.noemie_start_date,
                        covered_up.noemie_end_date],
                    from_=[q_table, item2],
                    values=[Coalesce(NullIf(q_table.o_m_start_date, date.max),
                                q_table.c_start_date),
                            Coalesce(
                                NullIf(Greatest(q_table.o_m_end_date,
                                    q_table.o_a_end_date), date.min),
                                q_table.c_end_date)],
                    where=(covered_up.party == q_table.party) & (
                        item2.id == covered_up.item_desc) & (
                        item2.is_noemie == Literal(True)) & (
                        covered_up.party != Null)))

    @fields.depends('item_desc')
    def on_change_with_is_noemie(self, name=''):
        return self.item_desc and self.item_desc.is_noemie

    @fields.depends('noemie_return_code', 'is_noemie')
    def on_change_with_noemie_status(self, name=''):
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

    def update_noemie_dates(self):
        if self.party and self.item_desc.is_noemie:
            prev_start_date = getattr(self, 'noemie_start_date', None)
            prev_end_date = getattr(self, 'noemie_end_date', None)
            if self.contract_status == 'void' or all(
                    [o.status == 'void' for o in self.options]):
                if self.noemie_start_date:
                    self.noemie_end_date = self.noemie_start_date + \
                        relativedelta(days=1)
                else:
                    self.noemie_end_date = None
            CoveredElement = Pool().get('contract.covered_element')
            covered_elements = CoveredElement.search([
                    ('id', '!=', self.id),
                    ('item_desc.is_noemie', '=', True),
                    ('party', '=', self.party.id)])
            if covered_elements:
                self.noemie_return_code = covered_elements[0].noemie_return_code
                self.noemie_update_date = covered_elements[0].noemie_update_date
                self.noemie_start_date = min(
                    covered_elements[0].noemie_start_date, self.start_date)
                if covered_elements[0].noemie_end_date:
                    self.noemie_end_date = max(
                        covered_elements[0].noemie_end_date,
                        getattr(self, 'end_date', None) or date.min)
                else:
                    self.noemie_end_date = getattr(self, 'end_date', None)
            else:
                self.noemie_start_date = getattr(self, 'noemie_start_date',
                    None) or self.start_date
                self.noemie_end_date = getattr(self, 'end_date', None)
                self.noemie_return_code = getattr(self, 'noemie_return_code',
                    '')
                self.noemie_update_date = getattr(self, 'noemie_update_date',
                    None)
                self.noemie_status = getattr(self, 'noemie_status', 'waiting')
            if self.party and self.party.health_complement:
                print([x.date for x in self.party.health_complement])
                print(list(self.party.health_complement))
                health_complement = sorted(list(self.party.health_complement),
                    key=lambda x: x.date or date.min)[-1]
                if health_complement.date:
                    self.noemie_start_date = max(health_complement.date,
                        self.noemie_start_date)
            if self.contract_status == 'void' or all(
                    [o.status == 'void' for o in self.options]):
                self.noemie_end_date = self.noemie_start_date
            if (prev_start_date != self.noemie_start_date) or \
                    (prev_end_date != self.noemie_end_date):
                self.noemie_return_code = ''
                self.noemie_status = self.on_change_with_noemie_status()
                for covered in covered_elements:
                    covered.noemie_start_date = self.noemie_start_date
                    covered.noemie_end_date = self.noemie_end_date
                    covered.noemie_return_code = ''
                if covered_elements:
                    CoveredElement.save(covered_elements)

    def recalculate(self):
        super().recalculate()
        self.update_noemie_dates()

    def notify_contract_end_date_change(self, new_end_date):
        res = super().notify_contract_end_date_change(new_end_date)
        if new_end_date:
            self.noemie_end_date = max(new_end_date,
                self.noemie_end_date or date.min)
        return res

    @fields.depends('noemie_return_code', 'noemie_update_date', 'noemie_status',
        'start_date', 'end_date', 'is_noemie')
    def on_change_party(self):
        super().on_change_party()

    @fields.depends('noemie_return_code', 'noemie_update_date', 'noemie_status',
        'start_date', 'end_date', 'is_noemie')
    def on_change_item_desc(self):
        super().on_change_item_desc()

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

    def update_item_desc(self):
        res = super().update_item_desc()
        self.is_noemie = self.on_change_with_is_noemie()
        return res
