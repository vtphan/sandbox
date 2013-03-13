import json
from config import red
from flask import request, Blueprint


sse_bp = Blueprint('sse', __name__, template_folder='templates')

sse_events = {}

# look up how redis handles sets.
# sse_channels = red.set('sse-channels')

# ----------------------------------------------------------------------------
def on_event(ev):
   '''
      @on_event('some_event')
      def f(message, cid):
         # This function must take 2 parameters message and channel id (cid)
         # What this function returns is ignored
         pass
   '''
   if ev not in sse_events:
      sse_events[ev] = []

   def deco(f):
      sse_events[ev].append(f)
      return f

   return deco

# ----------------------------------------------------------------------------

def publish(message, cid):
   # cid = None, publish all channels
   # cid = <int>, publish to all clients listening to this channel

   red.publish('sse-%s' % cid, u'%s' % json.dumps(message))

# ----------------------------------------------------------------------------

def listen(cid, from_cid):
   ''' listen to channel cid, from the client identified by channel from_cid '''
   pass

# ----------------------------------------------------------------------------
#
# Client sends messages to server via sse_send
#
# ----------------------------------------------------------------------------
@sse_bp.route('/sse_send', methods=['POST'])
def sse_send():
   ev = request.form['event']
   message = request.form['message']

   # the channel that sends the message
   cid = request.form['cid']

   for f in sse_events.get(e, []):
      f(message, cid)

   return ''

# ----------------------------------------------------------------------------
#
# Client receives streaming message (event-source) from this handle
#
# ----------------------------------------------------------------------------
@sse_bp.route('/sse_receive/<int:cid>')
def sse_receive(cid):
   def event_stream():
      pubsub = red.pubsub()
      pubsub.subscribe('sse-%s' % cid)
      for message in pubsub.listen():
         yield 'data: {0}\n\n'.format(message['data'])

   return Response(event_stream(), mimetype="text/event-stream")

# ----------------------------------------------------------------------------

# @app.route('/sse_send', methods=['POST'])
# def sse_send():
#    mesg_type = request.form['type']
#    message = request.form['message']
#    chanid = request.form['chanid']

#    stream_message = { 'chanid' : chanid }
#    if mesg_type == 'chat':
#       user = auth.get_logged_in_user()
#       now = datetime.datetime.now().replace(microsecond=0).time()
#       stream_message.update(chat=request.form['message'], time=now.strftime('%I:%M'), username=user.username, uid=user.id)

#    elif mesg_type == 'code':
#       output = execute_python_code(message)
#       stream_message.update(output=output, code=message)

#    elif mesg_type == 'code_noexec':
#       stream_message.update(code=message)

#    red.publish('sandbox', u'%s' % json.dumps(stream_message))
#    return ''