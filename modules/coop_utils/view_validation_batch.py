from trytond.pool import Pool

import batchs

__all__ = [
    'ViewValidationBatch',
]


class ViewValidationBatch(batchs.BatchRoot):
    'View validation batch'

    __name__ = 'ir.ui.view.validate'

    @classmethod
    def get_batch_main_model_name(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_search_model(cls):
        return 'ir.ui.view'

    @classmethod
    def get_batch_name(cls):
        return 'View validation batch'

    @classmethod
    def get_batch_stepping_mode(cls):
        return 'divide'

    @classmethod
    def get_batch_step(cls):
        return 4

    @classmethod
    def get_batch_domain(cls):
        Module = Pool().get('ir.module.module')
        modules = Module.search([])
        utils_module = Module.search([('name', '=', 'coop_utils')])[0]
        coop_modules = set([module.name for module in modules
            if utils_module in module.parents])
        return [('module', 'in', coop_modules)]

    @classmethod
    def execute(cls, objects, ids, logger):
        for view in objects:
            try:
                full_xml_id = view.xml_id
                if full_xml_id == '':
                    continue
                xml_id = full_xml_id.split('.')[-1]
                if view.inherit:
                    full_inherited_xml_id = view.inherit.xml_id
                    if full_inherited_xml_id.split('.')[-1] != xml_id:
                        logger.warning('View %s inherits from %s but has different '
                            'id !' % (full_xml_id, full_inherited_xml_id))
            except:
                logger.error('Failed testing view %s' % view.id)
                raise
