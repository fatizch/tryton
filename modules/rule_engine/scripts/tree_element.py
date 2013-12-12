from proteus import Model


def write_header(f):
    f.write(u'<?xml version="1.0"?>\n')
    f.write(u'<tryton>\n')
    f.write(u'    <data>\n')


def write_footer(f):
    f.write(u'    </data>\n')
    f.write(u'</tryton>\n')


def write_record(f, te, parent=None):
    id = te.translated_technical_name
    record = u'''        <record model="rule_engine.tree_element" id="%s">
            <field name="translated_technical_name">%s</field>
            <field name="description">%s</field>
            <field name="type">%s</field>
            <field name="language" ref="ir.lang_%s"/>''' % (
        id,
        te.translated_technical_name,
        te.description,
        te.type,
        te.language.code[0:2])
    if te.namespace:
        record += u'\n            <field name="namespace">%s</field>' % te.namespace
    if te.name:
        record += u'\n            <field name="name">%s</field>' % te.name
    if te.fct_args:
        record += u'\n            <field name="fct_args">%s</field>' % te.fct_args
    if te.long_description:
        record += u'\n            <field name="long_description">%s</field>' % te.long_description
    if parent:
        record += u'\n            <field name="parent" ref="%s"/>' % parent
    record += '\n        </record>\n'
    f.write(record.encode('utf-8'))
    if not parent:
        record = u'''        <record model="rule_engine.context-function" id="cte_default_%s">
            <field name="context" ref="rule_engine.default_context"/>
            <field name="tree_element" ref="%s"/>
        </record>\n''' % (id, id)
        f.write(record.encode('utf-8'))
    for children in te.children:
        write_record(f, children, id)


def export_tree_elements(cfg_dict, f):
    TreeElement = Model.get('rule_engine.tree_element')
    for te in TreeElement.find([('parent', '=', None)]):
        write_record(f, te)


def export_configuration(cfg_dict):
    with open('tree_element.xml', 'w') as f:
        write_header(f)
        export_tree_elements(cfg_dict, f)
        write_footer(f)
