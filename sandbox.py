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

      all_records = StudentRecord.all_online()

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
   teachers = StudentRecord.get_all( lambda v: v.is_teacher == True)
   m = dict(cid=channel, chat=message, chat_id=chat_id(), uid=chatter.id, username=chatter.username)
   sse.broadcast(channel, m, m, additional_channels=teachers.keys(), event='chat')

# ----------------------------------------------------------------------------
# client "guest" joins channel "host"
# TODO: pass along all users joining the channel
# ----------------------------------------------------------------------------
@sse.on_event('join')
def event_join(host, guest):
   records = StudentRecord.all_online()
   guest_record = records[int(guest)]
   host_record = records[int(host)]
   host_channel = sse.current_channel(host)

   guest_channel = sse.current_channel(guest)
   sse.listen_to(host, guest)

   m = dict(cid=guest, host_cid=host, board_status=host_record.open_board)

   if host!=guest and int(host)!=int(host_channel):
      # host is elsewhere
      host_of_host = records[int(host_channel)]
      m.update(notice = "%s is visiting %s's sandbox" % (host_record.username, host_of_host.username))

   if guest_record.is_teacher or guest==host:
      pids = red.smembers('published-problems')
      pids = sorted(int(p) for p in pids)
      m.update(pids=pids, total_score=sum(host_record.scores.values()),
         brownies=host_record.brownies)

   sse.notify( { guest : m } , event='join')

   ## Inform old channel and new channel of updated listeners list
   guest_listeners = [ records[int(i)].username for i in sse.listening_clients(guest_channel) ]
   m = dict(host_cid=guest_channel, listeners=guest_listeners)
   sse.broadcast(guest_channel, m, m, event='listeners-update')

   host_listeners = [ records[int(i)].username for i in sse.listening_clients(host) ]
   m = dict(host_cid=host, listeners=host_listeners)
   sse.broadcast(host, m, m, event='listeners-update')

   # print '%s leaves; inform %s with %s' % (guest, guest_channel, guest_listeners)
   # print '%s joins; inform %s with %s' % (guest, host, host_listeners)


# ----------------------------------------------------------------------------
# sandbox view
# ----------------------------------------------------------------------------
@sandbox_bp.route('/')
@auth.login_required
def index():
   logged_in_user = auth.get_logged_in_user()

   user_record = StudentRecord(logged_in_user.id)
   user_record.username = logged_in_user.username
   user_record.online = True
   if logged_in_user.role == 'teacher':
      user_record.open_board = True
      user_record.is_teacher = True
   user_record.save()

   all_users = auth.User.select()
   all_records = StudentRecord.all_online()

   # notify those who can view boards that the client is online
   messages = {}
   for c, r in all_records.items():
      if user_record.id != c and (r.is_teacher or user_record.open_board):
         messages[c] = dict(cid=user_record.id, board_status=user_record.open_board)
   sse.notify(messages, event='online')

   problem_ids = red.smembers('published-problems')
   listeners=[all_records[int(i)].username for i in sse.listening_clients(user_record.id) if int(i) in all_records]

   return render_template('sandbox.html', problem_ids=problem_ids, sum=sum,
      user_record = user_record,
      all_records = all_records,
      all_users = all_users,
      listeners = listeners)

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