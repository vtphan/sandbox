import os
import tempfile
import random
import string
import subprocess
from subprocess import check_output, CalledProcessError
import time
import datetime
import redis

from flask import Flask, Response, jsonify, render_template, session, request, redirect, url_for
app = Flask(__name__)
app.debug = True

red = redis.StrictRedis()

@app.route('/post', methods=['POST'])
def post():
	message = request.form['message']
	user = session.get('user', 'anonymous')
	now = datetime.datetime.now().replace(microsecond=0).time()
	red.publish('chat', u'[%s] %s: %s<br/>' % (now.isoformat(), user, message))
	return ''

@app.route('/stream')
def stream():
	def event_stream():
		pubsub = red.pubsub()
		pubsub.subscribe('chat')
		for message in pubsub.listen():
			yield 'data: %s\n\n' % message['data']

	return Response(event_stream(), mimetype="text/event-stream")


@app.route('/')
def index():
	return render_template('index.html')

@app.route('/whiteboard')
def whiteboard():
	return render_template('whiteboard.html')

##--------------------------------------------------------------------------
def exec_func(code_file):
	try:
		output = check_output(['/usr/local/bin/python', code_file], stderr=subprocess.STDOUT)
	except CalledProcessError as err:
		output = err.output
	return output.replace('\n', '<br>')


@app.route('/_run')
def run():
	code = request.args.get('code', '')
	code = code.replace(u'\xa0', u' ')
	# print "==>Run: ", code
	fn = 'sb_' + ''.join(random.choice(string.letters) for i in xrange(20)) + '.py'
	fn = os.path.join(tempfile.mkdtemp(), fn)
	with open(fn, 'w') as f:
		f.write(code)
	output = exec_func(fn)
	return jsonify(result = output)




if __name__ == "__main__":
	app.run()

