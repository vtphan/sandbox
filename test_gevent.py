import gevent
from gevent import pywsgi
import time

def handle(environ, start_response):
    start_response('200 OK', [('Content-Type', 'text/html')])
    yield ' ' * 1200
    yield '<html><body><h1>Hi '
    for i in range(10000):
    	for j in range(10000):
    		i+j
    yield 'There</h1></body></html>'

server = pywsgi.WSGIServer(('127.0.0.1', 1234), handle)
print "Serving on http://127.0.0.1:1234..."
server.serve_forever()