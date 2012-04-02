from trytond.model import ModelSQL, ModelView, fields

class Opportunity(ModelSQL, ModelView):
    'Opportunity'
    _description = __doc__
    _name = 'training.opportunity'
    _rec_name = 'description'
    description = fields.Char('Description', required=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date')
    party = fields.Many2One('party.party', 'Party', required=True)
    comment = fields.Text('Comment')
    
Opportunity()
