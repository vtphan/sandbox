import os
import tempfile
import random
import string
import subprocess
from subprocess import check_output, CalledProcessError
import time
import datetime

from flask import Blueprint, render_template, session, request, redirect, url_for, flash
import sse
from config import app, auth, red
from student_record import StudentRecord

sandbox_bp = Blueprint('sandbox', __name__, url_prefix='/sandbox', template_folder='templates')

# @app.route('/toggle_board/<int:uid>')
# @auth.login_required
# def toggle_board(uid):
#    user = auth.get_logged_in_user()
#    if user.id == uid or user.role == 'teacher':
#       s = UserRecord(uid)
#       s.open_board = not s.open_board
#       s.save()
#       broadcast_status(s)
#       return 'open' if s.open_board else 'closed'
#    return 'illegal'

# def broadcast_status(user):
#    stream_message = { 'chanid' : user.id, 'update' : user.as_dict() }
#    red.publish('sandbox', u'%s' % json.dumps(stream_message))

# ----------------------------------------------------------------------------
# Event listeners
# ----------------------------------------------------------------------------
@sse.on_event('run-code')
def event_run_code(message, cid):
   output = execute_python_code(message)
   to_others = dict(output=output, code=message)
   to_self = dict(output=output)
   sse.broadcast(cid, to_others, to_self)

# ----------------------------------------------------------------------------
@sse.on_event('send-code')
def event_run_code(message, cid):
   to_others = dict(code=message)
   sse.broadcast(cid, to_others, None)

# ----------------------------------------------------------------------------
@sse.on_event('chat')
def event_chat(message, cid):
   user = auth.get_logged_in_user()
   now = datetime.datetime.now().replace(microsecond=0).time()
   m = dict(chat=message, time=now.strftime('%I:%M'), username=user.username, uid=user.id)
   channel = red.hget('sse-listening', cid)
   sse.broadcast(channel, m, m)

# ----------------------------------------------------------------------------
@sse.on_event('join')
def event_join(joining_channel, cid):
   sse.listen_to(joining_channel, cid)

# ----------------------------------------------------------------------------
# sandbox view
# ----------------------------------------------------------------------------
@sandbox_bp.route('/')
@auth.login_required
def index():
   logged_in_user = auth.get_logged_in_user()

   user_record = StudentRecord(logged_in_user.id)
   if logged_in_user.role == 'teacher':
      user_record.view_all_boards = True
      user_record.open_board = True
   user_record.save()

   all_users = auth.User.select()
   all_records = StudentRecord.get_all()

   return render_template('sandbox.html',
      user_record = user_record,
      all_records = all_records,
      logged_in_user = logged_in_user,
      all_users = all_users)

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