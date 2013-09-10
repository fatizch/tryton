import httplib
import simplejson


def get_trytond_response(db_name, method, params, session=None):
    if session:
        params = session + params
    conn = httplib.HTTPConnection("localhost:8000")
    print simplejson.dumps(params)
    print '{"method": "%s", "params":%s, "id": 1}' % (method, simplejson.dumps(params))
    conn.request("POST", "/%s" % db_name,
        '{"method": "%s", "params":%s, "id": 1}' % (method, simplejson.dumps(params)))
    response = conn.getresponse()
    if not response.reason == 'OK':
        print 'WS Error'
        return response.read()
    return simplejson.loads(response.read())


def get_session(db_name):
    res = get_trytond_response(db_name, 'common.db.login', ["admin", "admin"])
    if res:
        return res["result"]

def get_products(db_name, session):
    get_trytond_response(db_name, "model.offered.product.read",
        [[1, 2], ["name"], {}], session)

if __name__ == '__main__':
    db_name = 'mali'
    session = get_session(db_name)
    print get_products(db_name, session)
