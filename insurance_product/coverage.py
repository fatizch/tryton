#-*- coding:utf-8 -*-
import copy

from trytond.model import fields
from trytond.pool import Pool
from trytond.pyson import Eval, Bool

from trytond.modules.coop_utils import model, business, utils
from trytond.modules.insurance_product import Offered
from trytond.modules.insurance_product import PricingResultLine
from trytond.modules.insurance_product import EligibilityResultLine


__all__ = [
    'Coverage'
    ]


class Coverage(model.CoopSQL, Offered):
    'Coverage'

    __name__ = 'ins_product.coverage'
    _export_name = 'code'

    insurer = fields.Many2One('party.insurer', 'Insurer')
    family = fields.Selection([('default', 'default')], 'Family',
        required=True)
    benefits = fields.One2Many('ins_product.benefit', 'coverage', 'Benefits',
        context={'start_date': Eval('start_date'),
                 'currency_digits': Eval('currency_digits')},
        states={'readonly': ~Bool(Eval('start_date'))},
        depends=['currency_digits'])
    currency = fields.Many2One('currency.currency', 'Currency', required=True)
    coverage_amount_mgr = model.One2ManyDomain(
        'ins_product.business_rule_manager',
        'offered', 'Coverage Amount Manager')
    covered_dynamic_data_manager = model.One2ManyDomain(
        'ins_product.dynamic_data_manager',
        'master',
        'Covered Dynamic Data Manager',
        context={
            'for_kind': 'sub_elem',
            'schema_element_kind': 'sub_elem'},
        domain=[('kind', '=', 'sub_elem')],
        size=1)

    @classmethod
    def delete(cls, entities):
        utils.delete_reference_backref(
            entities,
            'ins_product.business_rule_manager',
            'offered')
        utils.delete_reference_backref(
            entities,
            'ins_product.dynamic_data_manager',
            'master')
        super(Coverage, cls).delete(entities)

    @classmethod
    def __setup__(cls):
        super(Coverage, cls).__setup__()
        #Temporary remove, while impossible to duplicate whith same code
#        cls._sql_constraints += [
#            ('code_uniq', 'UNIQUE(code)', 'The code must be unique!'),
#        ]
        for field_name in (mgr for mgr in dir(cls) if mgr.endswith('_mgr')):
            cur_attr = copy.copy(getattr(cls, field_name))
            if not hasattr(cur_attr, 'context') or not isinstance(
                    cur_attr, fields.Field):
                continue
            if cur_attr.context is None:
                cur_attr.context = {}
            cur_attr.context['for_family'] = Eval('family')
            cur_attr = copy.copy(cur_attr)
            setattr(cls, field_name, cur_attr)

    def give_me_price(self, args):
        # This method is one of the core of the pricing system. It asks for the
        # price for the self depending on the contrat that is given as an
        # argument.
        data_dict, errs = utils.get_data_from_dict(['contract', 'date'], args)
        if errs:
            # No contract means no price.
            return (None, errs)
        contract = data_dict['contract']
        date = data_dict['date']

        # We need to chack that self is part of the subscribed coverages of the
        # contract.
        coverages = contract.get_active_coverages_at_date(date)
        res = PricingResultLine(name=self.name)
        if self in coverages:
            # The first part of the pricing is the price at the coverage level.
            # It is computed by the pricing manager, so we just need to forward
            # the request.
            try:
                _res, _errs = self.get_result('price', args, manager='pricing')
            except utils.NonExistingManagerException:
                _res = None
                _errs = []
            if _res and _res.value:
                # If a result exists, we give it a name and add it to the main
                # result
                for_option = contract.get_option_for_coverage_at_date(
                    self, date)
                if for_option:
                    if for_option.id:
                        _res.on_object = '%s,%s' % (
                            for_option.__name__, for_option.id)
                    else:
                        _res.name = 'Global Price'
                res += _res
                res.on_object = '%s,%s' % (
                    self.__name__, self.id)
            # We always append the errors (if any).
            errs += _errs

            # Now it is time to price the covered elements of the contract.
            # Note that they might have a role in the Base Price computation,
            # depending on the algorithm that is used.
            #
            # What we compute now is the part of the price that is associated
            # to each of the covered elements at the given date
            for covered, covered_data in self.give_me_covered_elements_at_date(
                    args)[0]:
                # Now we need to set a new argument before forwarding
                # the request to the manager, which is the covered
                # element it must work on.
                tmp_args = args
                tmp_args['sub_elem'] = covered
                tmp_args['data'] = covered_data

                # And we finally call the manager for the price
                try:
                    _res, _errs = self.get_result(
                        'sub_elem_price',
                        tmp_args,
                        manager='pricing')
                except utils.NonExistingManagerException:
                    _res = None
                    _errs = []
                if _res and _res.value:
                    # Basically we set name = covered.product_specific
                    # .person.name, but 'product_specific' is a
                    # Reference field and is not automatically turned
                    # into a browse object.
                    # Should be done later by tryton.
                    _res.name = covered.get_name_for_info()
                    if covered_data.id:
                        _res.on_object = '%s,%s' % (
                            covered_data.__name__,
                            covered_data.id)
                    res += _res
                    errs += _errs
            errs = list(set(errs))
            if 'Could not find a matching manager' in errs:
                errs.remove('Could not find a matching manager')
            return (res, list(set(errs)))
        return (None, [])

    def get_dates(self):
        # This is a temporary functionnality that is provided to ease the
        # checking of the pricing calculations.
        # In 'real life', it is not systematic to update the pricing when a new
        # version of the rule is defined.
        res = set()
        if self.pricing_mgr and len(self.pricing_mgr) == 1:
            for rule in self.pricing_mgr[0].business_rules:
                res.add(rule.start_date)
        return res

    def give_me_eligibility(self, args):
        try:
            res = self.get_result('eligibility', args, manager='eligibility')
        except utils.NonExistingManagerException:
            return (EligibilityResultLine(True), [])
        return res

    def give_me_sub_elem_eligibility(self, args):
        try:
            res = self.get_result(
                'sub_elem_eligibility', args, manager='eligibility')
        except utils.NonExistingManagerException:
            return (EligibilityResultLine(True), [])
        return res

    @staticmethod
    def default_currency():
        return business.get_default_currency()

    def give_me_family(self, args):
        return (Pool().get(self.family), [])

    def give_me_extension_field(self, args):
        return self.give_me_family(args)[0].get_extension_model()

    def give_me_covered_elements_at_date(self, args):
        contract = args['contract']
        date = args['date']
        res = []
        good_ext = self.give_me_extension_field(args)
        if not good_ext or not hasattr(contract, good_ext):
            return [], ['Extension not found']
        for covered in getattr(contract, good_ext)[0].covered_elements:
            # We must check that the current covered element is
            # covered by self.
            for covered_data in covered.covered_data:
                for_coverage = utils.convert_ref_to_obj(
                    covered_data.for_coverage)
                if not for_coverage.code == self.code:
                    continue

                # And that this coverage is effective at the requested
                # computation date.
                if not (date >= covered_data.start_date and
                        (not hasattr(covered_data, 'end_date') or
                            covered_data.end_date is None or
                            covered_data.end_date < date)):
                    continue
                res.append((covered, covered_data))
        return res, []

    def is_valid(self):
        if self.template_behaviour == 'remove':
            return False
        return True

    def get_rec_name(self, name):
        return '(%s) %s' % (self.code, self.name)

    def give_me_allowed_amounts(self, args):
        try:
            return self.get_result(
                'allowed_amounts',
                args,
                manager='coverage_amount')
        except utils.NonExistingManagerException:
            return [], []

    def give_me_coverage_amount_validity(self, args):
        try:
            return self.get_result(
                'coverage_amount_validity',
                args,
                manager='coverage_amount')
        except utils.NonExistingManagerException:
            return (True, []), []

    @classmethod
    def search_rec_name(cls, name, clause):
        if cls.search([('code',) + clause[1:]], limit=1):
            return [('code',) + clause[1:]]
        return [(cls._rec_name,) + clause[1:]]

    def give_me_dynamic_data_ids_aggregate(self, args):
        if not 'dd_args' in args:
            return [], []
        dd_args = args['dd_args']
        if not self.give_me_family(args)[0].get_extension_model() \
                == dd_args['path'] and not dd_args['path'] == 'all':
            return [], []
        if not('options' in dd_args and dd_args['options'] != '' and
                self.code in dd_args['options'].split(';')):
            return [], []
        if dd_args['kind'] == 'main':
            return self.give_me_dynamic_data_ids(args)
        elif dd_args['kind'] == 'sub_elem':
            return self.give_me_covered_dynamic_data_ids(args)
        return [], []

    def give_me_covered_dynamic_data_ids(self, args):
        if not(hasattr(self,
                'covered_dynamic_data_manager') and
                self.covered_dynamic_data_manager):
            return []
        return self.covered_dynamic_data_manager[0].get_valid_schemas_ids(
            args['date']), []
