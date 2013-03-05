import os
import tempfile
import json
import random
import string
import subprocess
from subprocess import check_output, CalledProcessError
import time
import datetime
import redis

from flask import Flask, Response, jsonify, render_template, session, request,\
	redirect, url_for, flash
from flask_peewee.db import Database
from peewee import *
from auth import Auth

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
@auth.after_login
def after_login():
	user = auth.get_logged_in_user()
	session['view_everyone_sandbox'] = user.role=='teacher'

# ----------------------------------------------------------------------------
# Sandbox management
# ----------------------------------------------------------------------------

@app.route('/sandbox')
@app.route('/sandbox/<int:uid>')
@auth.login_required
def sandbox(uid=None):
	if uid is not None:
		try:
			user = auth.User.get(auth.User.id == uid)
		except auth.User.DoesNotExist:
			flash('User does not exist')
			return redirect(url_for('index'))

		cur_user = auth.get_logged_in_user()
		show_editor = (cur_user.id == uid)

		# if cur_user.id != uid and session['view_everyone_sandbox'] == False:
		# 	flash('You can only view your own sandbox at this time.')
		# 	return redirect(url_for('index'))
	else:
		user = auth.get_logged_in_user()
		if user.role == 'teacher':
			return redirect(url_for('sandbox_teacher'))
		show_editor = True

	students=auth.User.select().where(auth.User.role=='student')

	return render_template('sandbox.html', channel_name=user.username,
		channel=user.id, show_editor=show_editor, students=students)

# ----------------------------------------------------------------------------

@app.route('/sandbox/teacher')
@auth.login_required
def sandbox_teacher():
	user = auth.get_logged_in_user()
	if user.role == 'teacher':
		show_editor = True
	else:
		show_editor = False

	return render_template('sandbox.html', channel_name='teacher',
		channel='teacher', show_editor=show_editor)

# ----------------------------------------------------------------------------
# Streaming, sending messages among channels
# ----------------------------------------------------------------------------
def execute_python_code(code):
	def run_code_now(code_file):
		try:
			output = check_output(['/usr/local/bin/python', code_file], stderr=subprocess.STDOUT)
		except CalledProcessError as err:
			output = err.output
		return output.replace('\n', '<br>')

	fn = 'sb_' + ''.join(random.choice(string.letters) for i in xrange(20)) + '.py'
	fn = os.path.join(tempfile.mkdtemp(), fn)
	with open(fn, 'w') as f:
		f.write(code)

	return run_code_now(fn)

# ----------------------------------------------------------------------------
@app.route('/send_message', methods=['POST'])
def send_message():
	mesg_type = request.form['type']
	message = request.form['message']
	channel = request.form['channel']

	if mesg_type == 'chat':
		user = auth.get_logged_in_user()
		now = datetime.datetime.now().replace(microsecond=0).time()
		m = '[%s] %s> %s<br/>' % (now.isoformat(), user.username, request.form['message'])
		stream_message = {'chat': m}

	elif mesg_type == 'code':
		# code = message.replace(u'\xa0', u' ')
		output = execute_python_code(message)
		stream_message = {'output':output, 'code':message}

	elif mesg_type == 'code_noexec':
		code = message.replace(u'\xa0', u' ')
		stream_message = {'code':code}

	stream_message = json.dumps({ 'channel-%s' % channel : stream_message })
	red.publish('channel-%s' % channel, u'%s' % stream_message)
	return ''

# ----------------------------------------------------------------------------
@app.route('/stream/<channel>')
def stream(channel):
	def event_stream():
		pubsub = red.pubsub()
		pubsub.subscribe('channel-%s' % channel)
		for message in pubsub.listen():
			yield 'data: {0}\n\n'.format(message['data'])

	return Response(event_stream(), mimetype="text/event-stream")


# ----------------------------------------------------------------------------
@app.route('/students')
@auth.role_required('teacher')
def students():
	return render_template('students.html', students=auth.User.select().where(auth.User.role=='student'))

# ----------------------------------------------------------------------------
# User management
# ----------------------------------------------------------------------------
def init_user_table():
   auth.User.create_table(fail_silently=True)
   if auth.User.select().count() == 0:
   	admin = auth.User(username='admin',email='admin@localhost')
   	admin.active = True
   	admin.admin = True
   	admin.role = 'teacher'
   	admin.set_password('password')
   	admin.save()

# ----------------------------------------------------------------------------
@app.route('/users', methods=['GET','POST'])
@auth.role_required('teacher')
def users():
	cur_user = auth.get_logged_in_user()

	if request.method == 'POST':
		user = auth.User(username=request.form['username'])
		user.email = request.form['username'] + '@memphis.edu'
		user.set_password(request.form['username'])
		user.active = True
		user.role = 'student'
		user.save()
		flash('user %d created' % user.id)
		return redirect(url_for('users'))
	return render_template('users.html', users=auth.User.select())

# ----------------------------------------------------------------------------
@app.route('/user/edit', methods=['GET','POST'])
@app.route('/user/edit/<int:uid>', methods=['GET','POST'])
@auth.role_required('teacher')
def user_edit(uid=None):
	cur_user = auth.get_logged_in_user()
	uid = cur_user.id if uid is None else uid
	user = cur_user if cur_user.id==uid else auth.User.get(auth.User.id==uid)

	if request.method == 'POST':
 		if 'delete' in request.form:
 			user.delete_instance()
 			flash('User %s is deleted' % user.username)
			return redirect(url_for('users'))
 		else:
			user.active = 'active' in request.form
			user.email = request.form['email']
			user.role = request.form['role']
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
	return render_template('index.html')

# ----------------------------------------------------------------------------

init_user_table()

if __name__ == "__main__":
	app.run()

