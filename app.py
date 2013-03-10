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

from student_record import UserRecord

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

# ----------------------------------------------------------------------------
# Sandbox management
# ----------------------------------------------------------------------------

@app.route('/toggle_board/<int:uid>')
@auth.login_required
def toggle_board(uid):
	user = auth.get_logged_in_user()
	if user.id == uid or user.role == 'teacher':
		s = UserRecord(uid)
		s.open_board = not s.open_board
		s.save()
		broadcast_status(s)
		return 'toggle board for user %s' % uid
	return 'cannot toggle board for user %s' % uid

# ----------------------------------------------------------------------------
@app.route('/sandbox')
@auth.login_required
def sandbox():
	logged_in_user = auth.get_logged_in_user()

	this_user = UserRecord(logged_in_user.id)
	if logged_in_user.role == 'teacher':
		this_user.view_all_boards = True
		this_user.open_board = True
	this_user.save()

	broadcast_status(this_user)

	all_users = auth.User.select()
	active_users = UserRecord.get_all()

	return render_template('sandbox.html', this_user=this_user,
		all_users=all_users, active_users=active_users, logged_in_user=logged_in_user)

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
def broadcast_status(user):
	stream_message = { 'chanid' : user.id, 'update' : user.as_dict() }
	red.publish('sandbox', u'%s' % json.dumps(stream_message))

# ----------------------------------------------------------------------------
@app.route('/send_message', methods=['POST'])
def send_message():
	mesg_type = request.form['type']
	message = request.form['message']
	chanid = request.form['chanid']

	stream_message = { 'chanid' : chanid }
	if mesg_type == 'chat':
		user = auth.get_logged_in_user()
		now = datetime.datetime.now().replace(microsecond=0).time()
		m = '<span class="time-light">%s</span> <strong>%s</strong>: %s<br/>' % (now.strftime('%I:%M'), user.username, request.form['message'])
		stream_message.update(chat=m)

	elif mesg_type == 'code':
		output = execute_python_code(message)
		stream_message.update(output=output, code=message)

	elif mesg_type == 'code_noexec':
		stream_message.update(code=message)

	red.publish('sandbox', u'%s' % json.dumps(stream_message))
	return ''

# ----------------------------------------------------------------------------
@app.route('/stream')
def stream():
	def event_stream():
		pubsub = red.pubsub()
		pubsub.subscribe('sandbox')
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

