import json
from config import red, app
from flask import request, Blueprint, Response


sse_bp = Blueprint('sse', __name__, template_folder='templates')

sse_events = {}

# ----------------------------------------------------------------------------
# Decorator for server-side listeners; used by sse_send
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
# Send messages to channels.
# Messages is a dict with keys being channels.
# ----------------------------------------------------------------------------
def notify(messages):
   pipe = red.pipeline()
   for channel, message in messages.items():
      pipe.publish('sse-%s' % channel, u'%s' % json.dumps(message))
   pipe.execute()

# ----------------------------------------------------------------------------
#
# Broadcast message to all clients listening to channel cid
# If message_to_host exists and cid is listening to its own channel,
#     message_to_host, not message, will be sent to cid.
#
# ----------------------------------------------------------------------------

def broadcast(cid, to_others, to_host = None):
   # all clients that are listening to channel cid
   clients = listening_clients(cid)
   pipe = red.pipeline()
   for c in clients:
      if c == str(cid):
         if to_host is not None:
            pipe.publish('sse-%s' % cid, u'%s' % json.dumps(to_host))
      else:
         pipe.publish('sse-%s' % c, u'%s' % json.dumps(to_others))
   pipe.execute()

# ----------------------------------------------------------------------------
#
# Goal: set client to listen to channel cid.  Must update 2 data structures.
# see-listening: hash storing the cid (value) to which a client (key) is currently listening
# clients-in-channel-<cid>: set storing all clients listening to channel cid
#
# ----------------------------------------------------------------------------

def listen_to(cid, client):
   current_cid = red.hget('current-channel', client)
   pipe = red.pipeline()
   if current_cid is None:
      # add client to the set of clients listening to cid
      pipe.sadd('clients-in-channel-%s' % cid, client)
   else:
      # moving client from current channel (current_cid) to new channel (cid)
      pipe.srem('clients-in-channel-%s' % current_cid, client)
      pipe.sadd('clients-in-channel-%s' % cid, client)

   # client will listen to channel cid
   pipe.hset('current-channel', client, cid)
   pipe.execute()

# ----------------------------------------------------------------------------
def listening_clients(cid):
   return red.smembers('clients-in-channel-%s' % cid)

# ----------------------------------------------------------------------------

def current_channel(client):
   return red.hget('current-channel', client)

# ----------------------------------------------------------------------------

def clear_all():
   red.flushdb()


# ----------------------------------------------------------------------------
# CLIENT SIDE
# ----------------------------------------------------------------------------

# ----------------------------------------------------------------------------
#
# Client sends messages to server via sse_send
#
# ----------------------------------------------------------------------------
@sse_bp.route('/sse_send', methods=['GET','POST'])
def sse_send():
   ev = request.form['event']
   message = request.form['message']

   # # the channel that sends the message
   cid = request.form['cid']

   for f in sse_events.get(ev, []):
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
      listen_to(cid, cid)
      for message in pubsub.listen():
         # print '>>>', cid, message['data']
         yield 'data: {0}\n\n'.format(message['data'])

   return Response(event_stream(), mimetype="text/event-stream")

# ----------------------------------------------------------------------------
