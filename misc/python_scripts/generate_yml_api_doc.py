import argparse
from trytond.config import parse_uri
from trytond.config import config as trytond_config
from proteus import config, Model
import yaml


def get_json_api_desc(api_name, config):
    splitted = api_name.split('.')
    method = splitted[-1]
    api_model = '.'.join(splitted[:-1])
    api = Model.get(api_model)
    description = getattr(api, method + '_description')(config.context)
    for inout in ('input', 'output'):
        schema = description['%s_schema' % inout]
        schema.update({'example': description['examples'][0][inout]})
        schema = {"%sSchema" % method + inout: schema}
        print(yaml.safe_dump(schema))


def main():
    parser = argparse.ArgumentParser(
            description='Generate YAML APIV2 Doc Elements')
    parser.add_argument('--database', '-d', required=True, help='Coog Database')
    parser.add_argument('--user', '-u', default='admin', help='Coog User')
    parser.add_argument('--password', '-p', default='admin',
            help='Coog User Password')
    parser.add_argument('--port', default='8000', help='Coog Server Port')
    parser.add_argument('--host', default='localhost', help='Coog Server Host')
    parser.add_argument('api',
            help='The API name. For example: api.party.upload_documents')
    arguments = parser.parse_args()

    proteus_conf = config.set_xmlrpc('http://%s:%s@%s:%s/%s/' % (
        arguments.user, arguments.password, arguments.host,
        arguments.port, arguments.database))

    get_json_api_desc(arguments.api, proteus_conf)


if __name__ == '__main__':
    main()
