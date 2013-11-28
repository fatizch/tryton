import xmlrpclib
import pprint


if __name__ == '__main__':
    user = 'lunalogic'
    password = '4V8bx6'
    db_name = 'demo_web_service'
    port = 8070
    server_address = 'coopengo.dtdns.net'

    # Get session
    s = xmlrpclib.ServerProxy('http://%s:%s@%s:%s/%s' %
        (user, password, server_address, port, db_name),
        allow_none=1, use_datetime=1)

    # Get the user context
    context = s.model.res.user.get_preferences(True, {})

    res = s.model.offered.product.get_product_def('kayes', context)
    pprint.pprint(res)
