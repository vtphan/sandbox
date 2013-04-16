import os
import tempfile
import random
import string
import subprocess
from subprocess32 import check_output, CalledProcessError, TimeoutExpired
import time
import datetime

from flask import Blueprint, render_template, session, request, redirect, url_for, flash
import sse
from config import app, auth, red
from student_record import StudentRecord

sandbox = Blueprint('sandbox', __name__, url_prefix='/sandbox', template_folder='templates')

TIMEOUT = 7

# ----------------------------------------------------------------------------

def chat_id():
   return red.incr('chat-count')

# ----------------------------------------------------------------------------
# Event listeners
# ----------------------------------------------------------------------------
@sse.on_event('toggle-board')
def event_toggle_board(message, cid):
   user = StudentRecord(cid)
   if user.username:
      record = StudentRecord(user.id)
      record.open_board = not record.open_board
      record.save()

      all_records = StudentRecord.online_students()

      message_to_all = {}
      listening_clients = sse.listening_clients(cid)
      for c, r in all_records.items():
         m = dict(cid=cid, board_status=record.open_board)
         if record.open_board == False and int(cid) != int(c):
            if not r.is_teacher and c in listening_clients:
               m.update(back_to_homeboard=True)
               sse.listen_to(c, c)
         message_to_all[c] = m

      sse.notify(message_to_all, event="toggle-board")

# ----------------------------------------------------------------------------
@sse.on_event('run-code')
def event_run_code(message, cid):
   output = execute_python_code(message)
   to_others = dict(cid=cid, output=output, code=message)
   to_self = dict(cid=cid, output=output)
   sse.broadcast(cid, to_others, to_self, event='run-code')

# ----------------------------------------------------------------------------
@sse.on_event('send-code')
def event_send_code(message, cid):
   to_others = dict(cid=cid, code=message)
   sse.broadcast(cid, to_others, None, event='send-code')

# ----------------------------------------------------------------------------
@sse.on_event('chat')
def event_chat(message, cid):
   chatter = StudentRecord(cid)
   channel = sse.current_channel(cid)
   teachers = StudentRecord.all_students( lambda v: v.is_teacher == True)
   m = dict(cid=channel, chat=message, chat_id=chat_id(), uid=chatter.id, username=chatter.username)
   sse.broadcast(channel, m, m, additional_channels=teachers.keys(), event='chat')

# ----------------------------------------------------------------------------
# client "guest" joins channel "host"
# ----------------------------------------------------------------------------
@sse.on_event('join')
def event_join(host, guest):
   online_students = StudentRecord.online_students()
   ## Key error is possible
   guest_record = online_students[int(guest)]
   host_record = online_students[int(host)]
   host_channel = sse.current_channel(host)
   guest_channel = sse.current_channel(guest)
   sse.listen_to(host, guest)

   m = dict(cid=guest, host_cid=host, board_status=host_record.open_board)

   if host!=guest and int(host)!=int(host_channel):
      # host is elsewhere
      host_of_host = online_students[int(host_channel)]
      m.update(notice = "%s is visiting %s's sandbox" % (host_record.username, host_of_host.username))

   if guest_record.is_teacher:
      pids = sorted(int(i) for i in red.smembers('published-problems'))
      scores = [ [p, host_record.scores.get(p,0)] for p in pids ]
      m.update(scores=scores, brownies=host_record.brownies)

   sse.notify( { guest : m } , event='join')

   ## Inform old channel and new channel of updated listeners list
   guest_listeners = [ online_students[int(i)].username for i in sse.listening_clients(guest_channel) ]
   m = dict(host_cid=guest_channel, listeners=guest_listeners)
   sse.broadcast(guest_channel, m, m, event='listeners-update')

   host_listeners = [ online_students[int(i)].username for i in sse.listening_clients(host) ]
   m = dict(host_cid=host, listeners=host_listeners)
   sse.broadcast(host, m, m, event='listeners-update')

# ----------------------------------------------------------------------------
# sandbox view
# ----------------------------------------------------------------------------
@sandbox.route('/')
@auth.login_required
def index():
   logged_in_user = auth.get_logged_in_user()

   user_record = StudentRecord(logged_in_user.id)
   user_record.online = True
   user_record.save()

   current_channel = sse.current_channel(user_record.id) or user_record.id

   all_users = auth.User.select()
   online_students = StudentRecord.online_students()
   listeners=[ online_students[int(i)].username \
      for i in sse.listening_clients(current_channel) if int(i) in online_students ]

   # notify those who can view boards that the client is online
   messages = {}
   for c, r in online_students.items():
      if user_record.id != c and (r.is_teacher or user_record.open_board):
         messages[c] = dict(cid=user_record.id, board_status=user_record.open_board)
   sse.notify(messages, event='online')

   problem_ids = sorted(int(i) for i in red.smembers('published-problems'))

   return render_template('sandbox.html',
      sum=sum, enumerate=enumerate,
      current_channel = current_channel,
      problem_ids=problem_ids,
      user_record = user_record,
      online_students = online_students,
      all_users = all_users,
      listeners = listeners)

# ----------------------------------------------------------------------------
def execute_python_code(code):
   def run_code_now(code_file):
      try:
         output = check_output(['/usr/local/bin/python', code_file], stderr=subprocess.STDOUT, timeout=TIMEOUT)
      except CalledProcessError as err:
         output = err.output
      except TimeoutExpired:
         return 'Timeout!!   You program took longer than %s seconds.' % TIMEOUT
      return output.replace('\n', '<br>')

   fn = 'sb_' + ''.join(random.choice(string.letters) for i in xrange(20)) + '.py'
   fn = os.path.join(tempfile.mkdtemp(), fn)
   with open(fn, 'w') as f:
      f.write(code)

   return run_code_now(fn)
