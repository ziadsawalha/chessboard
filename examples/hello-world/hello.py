"""Start a simple server that prints out the WSGI environment."""

from wsgiref import simple_server
from wsgiref import util


def simple_app(environ, start_response):
    """Start a relatively simple WSGI application.

    The application is going to print out the environment dictionary after
    being updated by setup_testing_defaults.
    """
    util.setup_testing_defaults(environ)

    status = '200 OK'
    headers = [('Content-type', 'text/plain')]

    start_response(status, headers)

    ret = ["%s: %s\n" % (key, value)
           for key, value in environ.iteritems()]
    return ret


SERVER = simple_server.make_server('', 8000, simple_app)
print "Serving on port 8000 (browse to http://127.0.0.1:8000)..."
SERVER.serve_forever()
# CTRL-C to end
