from trytond.model import ModelView, ModelSQL
from trytond.model import fields as fields

class Coverage(ModelSQL, ModelView):
    'Coverage'
    _name = 'ins_product.coverage'     
    _description = __doc__     
    name = fields.Char('Name', required=True, select=1)     
    code = fields.Char('Code', size=10,required=True, select=1)    
    managers = fields.One2Many('ins_product.businessrulemanager','belongs_to','Business rule managers')
    
Coverage()

class ProductOptionsCoverage(ModelSQL):
    'Define Product - Coverage relations'
    _name = 'ins_product-options-coverage'
    product = fields.Many2One('ins_product.product','Product',select=1, required=True)
    coverage = fields.Many2One('ins_product.coverage','Coverage',select=1, required=True)

ProductOptionsCoverage()	

class Product(ModelSQL, ModelView):
    'ins_product'     
    _name = 'ins_product.product'     
    _description = __doc__     
    name = fields.Char('Name', required=True, select=1)     
    code = fields.Char('Code', size=10,required=True, select=1)     
    options = fields.Many2Many('ins_product-options-coverage','product','coverage','Possible Options')

Product()

class BusinessRule(ModelSQL, ModelView):
    'Business rule'
    _name = 'ins_product.businessrule'
    _description = __doc__
    name = fields.Char('Name', required=True, select=1)     
    code = fields.Char('Code', size=10,required=True, select=1)
    manager = fields.Many2One('ins_product.businessrulemanager','Manager', required=True)    

BusinessRule()

class BusinessRuleManager(ModelSQL, ModelView):
    'Business rule manager'
    _name = 'ins_product.businessrulemanager'
    _description = __doc__
    name = fields.Char('Name', required=True, select=1)     
    code = fields.Char('Code', size=10,required=True, select=1)
    belongs_to = fields.Many2One('ins_product.coverage','Belongs to', required=True)
    business_rules = fields.One2Many('ins_product.businessrule','manager','Business rules')

BusinessRuleManager()
    
