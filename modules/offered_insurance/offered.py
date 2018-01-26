# -*- coding:utf-8 -*-
# This file is part of Coog. The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
from trytond.pool import PoolMeta
from trytond.pyson import Eval
from trytond.cache import Cache

from trytond.modules.coog_core import model, fields
from trytond.modules.coog_core import coog_string


__metaclass__ = PoolMeta
__all__ = [
    'Product',
    'ItemDescription',
    'ItemDescSubItemDescRelation',
    'ItemDescriptionExtraDataRelation',
    'CoveredElementEndReason',
    'ItemDescriptionEndReasonRelation',
    ]


class Product:
    __metaclass__ = PoolMeta
    __name__ = 'offered.product'

    item_descriptors = fields.Function(
        fields.Many2Many('offered.item.description', None, None,
            'Item Descriptions'),
        'on_change_with_item_descriptors')
    processes = fields.Many2Many('process-offered.product',
        'product', 'process', 'Processes')

    @classmethod
    def kind_list_for_extra_data_domain(cls):
        return ['contract', 'covered_element', 'option']

    @classmethod
    def __setup__(cls):
        super(Product, cls).__setup__()
        cls.extra_data_def.domain = [
            ('kind', 'in', cls.kind_list_for_extra_data_domain())]
        cls._error_messages.update({
                'missing_covered_element_extra_data': 'The following covered '
                'element extra data should be set on the product: %s',
                })

    @classmethod
    def validate(cls, instances):
        super(Product, cls).validate(instances)
        cls.validate_covered_element_extra_data(instances)

    @classmethod
    def validate_covered_element_extra_data(cls, instances):
        for instance in instances:
            from_option = set(extra_data for coverage in instance.coverages
                for extra_data in coverage.extra_data_def
                if extra_data.kind == 'covered_element')
            remaining = from_option - set(instance.extra_data_def)
            if remaining:
                instance.raise_user_error('missing_covered_element_extra_data',
                    (', '.join((extra_data.string
                                for extra_data in remaining))))

    @fields.depends('coverages')
    def on_change_with_item_descriptors(self, name=None):
        res = set()
        for coverage in self.coverages:
            if getattr(coverage, 'item_desc', None):
                res.add(coverage.item_desc.id)
        return list(res)

    def get_cmpl_data_looking_for_what(self, args):
        if 'elem' in args and args['level'] == 'option':
            return ''
        return super(Product, self).get_cmpl_data_looking_for_what(args)

    @classmethod
    def _export_light(cls):
        return super(Product, cls)._export_light() | {'processes'}


class ItemDescription(model.CoogSQL, model.CoogView, model.TaggedMixin):
    'Item Description'

    __name__ = 'offered.item.description'
    _func_key = 'code'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    extra_data_def = fields.Many2Many(
        'offered.item.description-extra_data',
        'item_desc', 'extra_data_def', 'Extra Data',
        domain=[('kind', '=', 'covered_element')], )
    kind = fields.Selection([
            ('', ''),
            ('party', 'Party'),
            ('person', 'Person'),
            ('company', 'Company'),
            ], 'Kind')
    kind_string = kind.translated('kind')
    sub_item_descs = fields.Many2Many(
        'offered.item.description-sub_item.description',
        'item_desc', 'sub_item_desc', 'Sub Item Descriptions',
        states={'invisible': Eval('kind') == 'person'})
    coverages = fields.One2Many('offered.option.description', 'item_desc',
        'Coverages', target_not_required=True)
    covered_element_end_reasons = fields.Many2Many(
        'offered.item.description-covered_element.end_reason', 'item_desc',
        'reason', 'Possible End Reasons')
    _check_sub_options_cache = Cache('has_sub_options')

    @classmethod
    def copy(cls, items, default=None):
        default = {} if default is None else default.copy()
        default.setdefault('coverages', None)
        return super(ItemDescription, cls).copy(items, default=default)

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coog_string.slugify(self.name)

    @classmethod
    def _export_skips(cls):
        result = super(ItemDescription, cls)._export_skips()
        result.add('coverages')
        return result

    @classmethod
    def _export_light(cls):
        return super(ItemDescription, cls)._export_light() | {'tags'}

    @classmethod
    def is_master_object(cls):
        return True

    def has_sub_options(self):
        cached = self.__class__._check_sub_options_cache.get(self.id, -1)
        if cached != -1:
            return cached
        value = any(x.coverages for x in self.sub_item_descs)
        self.__class__._check_sub_options_cache.set(self.id, value)
        return value


class ItemDescSubItemDescRelation(model.CoogSQL):
    'Relation between Item Desc and Sub Item Desc'

    __name__ = 'offered.item.description-sub_item.description'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE')
    sub_item_desc = fields.Many2One('offered.item.description',
        'Sub Item Desc', ondelete='RESTRICT')


class ItemDescriptionExtraDataRelation(model.CoogSQL):
    'Item Description to Extra Data Relation'

    __name__ = 'offered.item.description-extra_data'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE')
    extra_data_def = fields.Many2One('extra_data', 'Extra Data',
        ondelete='RESTRICT', )


class CoveredElementEndReason(model.CoogSQL, model.CoogView,
        model.TaggedMixin):
    'End reasons for covered elements'

    __name__ = 'covered_element.end_reason'
    _func_key = 'code'
    _rec_name = 'name'

    code = fields.Char('Code', required=True)
    name = fields.Char('Name', translate=True)
    item_descs = fields.Many2Many(
        'offered.item.description-covered_element.end_reason',
        'reason', 'item_desc', 'Item Descriptions')

    @classmethod
    def _export_skips(cls):
        return super(CoveredElementEndReason, cls)._export_skips() | {
            'item_descs'}

    @fields.depends('name', 'code')
    def on_change_with_code(self):
        if self.code:
            return self.code
        elif self.name:
            return coog_string.slugify(self.name)


class ItemDescriptionEndReasonRelation(model.CoogSQL):
    'Item Description to Covered Element End Reason relation'

    __name__ = 'offered.item.description-covered_element.end_reason'

    item_desc = fields.Many2One('offered.item.description', 'Item Desc',
        ondelete='CASCADE', select=True, required=True)
    reason = fields.Many2One('covered_element.end_reason', 'End Reason',
        ondelete='RESTRICT', select=True, required=True)
