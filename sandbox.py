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
from config import app, auth
from student_record import StudentRecord

sandbox_bp = Blueprint('sandbox', __name__, url_prefix='/sandbox', template_folder='templates')
# ----------------------------------------------------------------------------
# Event listeners
# ----------------------------------------------------------------------------
@sse.on_event('toggle-board')
def event_toggle_board(message, cid):
   user = auth.get_logged_in_user()
   if user and user.id == int(cid):
      record = StudentRecord(user.id)
      record.open_board = not record.open_board
      record.save()

      all_records = StudentRecord.get_all()

      message_to_all = {}
      listening_clients = sse.listening_clients(cid)
      for c, r in all_records.items():
         m = dict(cid=cid, board_status=record.open_board)
         if record.open_board == False and int(cid) != int(c):
            hide_board = not r.view_all_boards
            if hide_board and str(c) in listening_clients:
               m.update(back_to_homeboard=True)
               sse.listen_to(c, c)
            m.update(hide_board = hide_board)
         message_to_all[int(c)] = m

      sse.notify(message_to_all)

# ----------------------------------------------------------------------------
@sse.on_event('run-code')
def event_run_code(message, cid):
   output = execute_python_code(message)
   to_others = dict(cid=cid, output=output, code=message)
   to_self = dict(cid=cid, output=output)
   sse.broadcast(cid, to_others, to_self)

# ----------------------------------------------------------------------------
@sse.on_event('send-code')
def event_send_code(message, cid):
   to_others = dict(cid=cid, code=message)
   sse.broadcast(cid, to_others, None)

# ----------------------------------------------------------------------------
@sse.on_event('chat')
def event_chat(message, cid):
   user = auth.get_logged_in_user()
   now = datetime.datetime.now().replace(microsecond=0).time()
   channel = sse.current_channel(cid)
   m = dict(cid=channel, chat=message, time=now.strftime('%I:%M'), username=user.username, uid=user.id)
   sse.broadcast(channel, m, m)

# ----------------------------------------------------------------------------
@sse.on_event('join')
def event_join(joining_channel, cid):
   sse.listen_to(joining_channel, cid)
   if int(joining_channel) != int(cid):
      user_record = StudentRecord(int(joining_channel))
      m = dict(cid=cid, joining=True, which=user_record.id, board_status=user_record.open_board)
      sse.notify( { cid : m } )

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

   messages = {}
   for c, r in all_records.items():
      if int(user_record.id) != int(c) and (r.view_all_boards or user_record.open_board):
         messages[c] = dict(cid=user_record.id, just_joining = True, board_status=user_record.open_board)
   sse.notify(messages)

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