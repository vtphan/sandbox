import os
import tempfile
import random
import string
import subprocess
from subprocess import check_output, CalledProcessError
import time
import datetime
import redis

from flask import Flask, Response, jsonify, render_template, session, request,\
	redirect, url_for, flash
from flask_peewee.auth import Auth
from flask_peewee.db import Database
from peewee import *


# ----------------------------------------------------------------------------
DATABASE = { 'name': 'sandbox.db', 'engine': 'peewee.SqliteDatabase' }
DEBUG = True
SECRET_KEY = 'ssshhhh'

app = Flask(__name__)
app.config.from_object(__name__)

db = Database(app)
auth = Auth(app, db)
red = redis.StrictRedis()

# ----------------------------------------------------------------------------
@app.context_processor
def add_user_to_template():
    return dict(this_user=auth.get_logged_in_user())

# ----------------------------------------------------------------------------
# Whiteboard management
# ----------------------------------------------------------------------------

@app.route('/whiteboard')
@app.route('/whiteboard/<int:uid>')
@auth.login_required
def whiteboard(uid=None):
	user = auth.get_logged_in_user()
	if user.username != 'admin':
		return redirect(url_for('whiteboard'))

	if uid is not None:
		user = auth.User.get(auth.User.id == uid)

	return render_template('whiteboard.html', user=user)

# ----------------------------------------------------------------------------
@app.route('/send_code/<int:uid>', methods=['POST'])
def send_code(uid):
	code = request.form['code']
	red.publish('channel-in-%s' % uid, u'%s<br/>' % code)
	return ''

# ----------------------------------------------------------------------------
@app.route('/run_code/<int:uid>', methods=['POST'])
def run_code(uid):
	def run_code_now(code_file):
		try:
			output = check_output(['/usr/local/bin/python', code_file], stderr=subprocess.STDOUT)
		except CalledProcessError as err:
			output = err.output
		return output.replace('\n', '<br>')

	code = request.form['code']
	code = code.replace(u'\xa0', u' ')

	fn = 'sb_' + ''.join(random.choice(string.letters) for i in xrange(20)) + '.py'
	fn = os.path.join(tempfile.mkdtemp(), fn)
	with open(fn, 'w') as f:
		f.write(code)
	output = run_code_now(fn)

	red.publish('channel-out-%s' % uid, u'%s<br/>' % output)
	# return jsonify(result = output)
	return ''

# ----------------------------------------------------------------------------
@app.route('/stream/<c>/<int:uid>')
def stream(c, uid):
	def event_stream():
		pubsub = red.pubsub()
		pubsub.subscribe('channel-%s-%s' % (c, uid))
		for message in pubsub.listen():
			yield 'data: %s\n\n' % message['data']

	return Response(event_stream(), mimetype="text/event-stream")


# ----------------------------------------------------------------------------
# User management
# ----------------------------------------------------------------------------
def init_user_table():
   auth.User.create_table(fail_silently=True)
   if auth.User.select().count() == 0:
   	admin = auth.User(username='admin',email='admin@localhost',active=True)
   	admin.set_password('password')
   	admin.save()

# ----------------------------------------------------------------------------
@app.route('/users', methods=['GET','POST'])
@auth.login_required
def users():
	cur_user = auth.get_logged_in_user()
	if cur_user.username != 'admin':
		flash('you do not have permission to view this page')
		return redirect(url_for('index'))

	if request.method == 'POST':
		user = auth.User(username=request.form['username'])
		user.email = request.form['username'] + '@memphis.edu'
		user.set_password(request.form['username'])
		user.active = True
		user.save()
		flash('user %d created' % user.id)
		return redirect(url_for('users'))
	return render_template('users.html', users=auth.User.select())

# ----------------------------------------------------------------------------
@app.route('/user/edit', methods=['GET','POST'])
@app.route('/user/edit/<int:uid>', methods=['GET','POST'])
@auth.login_required
def user_edit(uid=None):
	cur_user = auth.get_logged_in_user()
	uid = cur_user.id if uid is None else uid
	if cur_user.username != 'admin' and cur_user.id != uid:
		flash('you do not have permission to view this page')
		return redirect(url_for('index'))

	user = cur_user if cur_user.id==uid else auth.User.get(auth.User.id==uid)

	if request.method == 'POST':
 		if 'delete' in request.form:
 			user.delete_instance()
 			flash('User %s is deleted' % user.username)
			return redirect(url_for('users'))
 		else:
			user.active = 'active' in request.form
			user.email = request.form['email']
			if request.form['new_password']:
				user.set_password(request.form['new_password'])
			user.save()
			flash('Information updated')
			return redirect(url_for('user_edit', uid=user.id))
	return render_template('user_edit.html', cur_user=cur_user, user=user)

# ----------------------------------------------------------------------------
@app.route('/logout')
@auth.login_required
def logout():
   user = auth.get_logged_in_user()
   auth.logout_user(user)
   return redirect(url_for('index'))

# ----------------------------------------------------------------------------
@app.route('/')
def index():
	u = auth.get_logged_in_user()
	return render_template('index.html')

# ----------------------------------------------------------------------------

init_user_table()

if __name__ == "__main__":
	app.run()

