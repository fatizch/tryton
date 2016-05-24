import re
import zipfile
from StringIO import StringIO
from collections import defaultdict

from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction
from trytond.wizard import Wizard, StateView, StateTransition, Button

from trytond.modules.cog_utils import model, fields


__all__ = [
    'ConvertTemplate',
    'SelectTemplatesForConversion',
    'MatchDisplayer',
    ]


class ConvertTemplate(Wizard):
    '''Convert Template

        A wizard to ease report template upgrades when modifying the underlying
        data structure
    '''
    __name__ = 'report.convert'

    start_state = 'select_templates'
    select_templates = StateView('report.convert.select_templates',
        'report_engine.convert_select_templates_view_form', [
            Button('Cancel', 'end', 'tryton-cancel'),
            Button('Convert', 'convert_templates', 'tryton-go-next',
                default=True, states={
                    'readonly': ~Eval('changes_calculated')})])
    convert_templates = StateTransition()

    @classmethod
    def __setup__(cls):
        super(ConvertTemplate, cls).__setup__()
        cls._error_messages.update({
                'search_for_none': 'Nothing is set for search, are you sure'
                ' you want to do this ?',
                'convert_ok_message': '%i occurences were converted',
                })

    def default_select_templates(self, name):
        defaults = {
            'search_for': '',
            'replace_with': '',
            'message': '',
            }
        if getattr(self, 'select_templates', None) and getattr(
                self.select_templates, 'templates', None):
            matches = sum([x.number_of_matches
                    for x in self.select_templates.templates])
            defaults['message'] = self.raise_user_error('convert_ok_message',
                (matches,), raise_exception=False)
        if Transaction().context.get('active_model') == 'report.template':
            defaults['templates'] = Transaction().context.get('active_ids')

        return defaults

    def transition_convert_templates(self):
        if not self.select_templates.search_for:
            self.raise_user_warning('search_for_none', 'search_for_none')
        Version = Pool().get('report.template.version')
        to_save = []
        per_template = defaultdict(list)
        for match in self.select_templates.matches:
            if match.to_update:
                per_template[Version(match.template_id)].append((match.match,
                        match.new_value))
        for template, matches in per_template.iteritems():
            template.data = self.replace_in_file(StringIO(template.data),
                matches)
            template.data = buffer(template.data.getvalue())
            to_save.append(template)
        if to_save:
            Version.save(to_save)
        return 'end'

    @classmethod
    def find_in_file(cls, data_in, search_for):
        '''
            Returns a list of placeholders matching search_for in data_in
        '''
        search_for = search_for.replace('"', '&quot;').replace("'", '&apos;')
        find_placeholders = re.compile('<text:placeholder ' +
            'text:placeholder-type="text">' +
            '&lt;(.*?)&gt;</text:placeholder>')
        with zipfile.ZipFile(data_in, 'r') as zin:
            for item in zin.infolist():
                if item.filename != 'content.xml':
                    continue
                return [x.replace('&quot;', '"').replace('&apos;', "'")
                    for x in re.findall(find_placeholders,
                        zin.read('content.xml'))
                    if search_for in x]

    @classmethod
    def replace_in_file(cls, data_in, matches):
        '''
            Updates data_in from matches. Matches is a list of tuples :

            [('replace', 'with')]
        '''
        def prepare_match(x):
            x = x.replace('"', '&quot;').replace("'", '&apos;')
            return '<text:placeholder text:placeholder-type="text">&lt;' + \
                x + '&gt;</text:placeholder>'

        data_out = StringIO()
        matches = [(prepare_match(x), prepare_match(y)) for x, y in matches]
        with zipfile.ZipFile(data_in, 'r') as zin, \
                zipfile.ZipFile(data_out, 'w') as zout:
            zout.comment = zin.comment  # Keep zip comment
            for item in zin.infolist():
                if item.filename != 'content.xml':
                    zout.writestr(item, zin.read(item.filename))
                else:
                    for search, replace in matches:
                        zout.writestr(item, zin.read(
                                'content.xml').replace(search, replace))
        return data_out


class SelectTemplatesForConversion(model.CoopView):
    'Select Templates for Conversion'

    __name__ = 'report.convert.select_templates'

    search_for = fields.Char('Search For', required=True)
    replace_with = fields.Char('Replace With')
    templates = fields.Many2Many('report.template', None, None, 'Templates',
        readonly=True)
    matches = fields.One2Many('report.convert.match', None,
        'Matches')
    changes_calculated = fields.Boolean('Changes calculated', states={
            'invisible': True})
    message = fields.Char('Completion Message', states={
            'invisible': ~Eval('message')}, readonly=True)

    @classmethod
    def __setup__(cls):
        super(SelectTemplatesForConversion, cls).__setup__()
        cls._buttons.update({
                'recalculate_matches': {
                    'readonly': ~Eval('search_for')}})

    @model.CoopView.button_change('changes_calculated', 'matches',
        'replace_with', 'search_for', 'templates')
    def recalculate_matches(self):
        pool = Pool()
        Converter = pool.get('report.convert', type='wizard')
        Displayer = pool.get('report.convert.match')
        new_matches = []
        for template in self.templates:
            for version in template.versions:
                if not version.data:
                    continue
                all_matches = Converter.find_in_file(StringIO(version.data),
                    self.search_for)
                for match in set(all_matches):
                    match = Displayer(to_update=bool(self.replace_with),
                        model_name=template.on_model.name, name=template.name,
                        language=version.language.name, match=match,
                        new_value=match, template_id=version.id)
                    if self.replace_with:
                        match.new_value = match.match.replace(self.search_for,
                            self.replace_with)
                    new_matches.append(match)
        self.matches = new_matches
        self.changes_calculated = True

    @fields.depends('changes_calculated', 'matches')
    def on_change_search_for(self):
        self.changes_calculated = False
        self.matches = []


class MatchDisplayer(model.CoopView):
    'Match Displayer'

    __name__ = 'report.convert.match'

    to_update = fields.Boolean('To Update', readonly=True)
    model_name = fields.Char('Model Name', readonly=True)
    name = fields.Char('Name', readonly=True)
    language = fields.Char('Language', readonly=True)
    match = fields.Char('Match', readonly=True)
    new_value = fields.Char('New Value')
    template_id = fields.Integer('Template Id', readonly=True)

    @fields.depends('match', 'new_value')
    def on_change_with_to_update(self):
        return self.match != self.new_value
