import json
from config import red, app
from flask import request, Blueprint, Response
from collection import Collection


sse_bp = Blueprint('sse', __name__, template_folder='templates')

sse_events = {}
channel_collection = Collection('channel', int, int)

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
def notify(messages, event='message'):
   pipe = red.pipeline()
   for channel, message in messages.items():
      pipe.publish('sse-%s' % channel, u'%s;%s' % (event, json.dumps(message)))
   pipe.execute()

# ----------------------------------------------------------------------------
#
# Broadcast message to all clients listening to channel cid
# If message_to_host exists and cid is listening to its own channel,
#     message_to_host, not message, will be sent to cid.
#
# ----------------------------------------------------------------------------

def broadcast(cid, to_others, to_host = None, event='message'):
   # all clients that are listening to channel cid
   clients = listening_clients(cid)
   pipe = red.pipeline()
   for c in clients:
      if c == str(cid):
         if to_host is not None:
            pipe.publish('sse-%s' % cid, u'%s;%s' % (event, json.dumps(to_host)))
      else:
         pipe.publish('sse-%s' % c, u'%s;%s' % (event, json.dumps(to_others)))
   pipe.execute()

# ----------------------------------------------------------------------------
#
# Goal: set client to listen to channel cid.
#
# ----------------------------------------------------------------------------

def listen_to(cid, client):
   channel_collection.insert(cid, client)

# ----------------------------------------------------------------------------
def listening_clients(channel):
   return channel_collection.members(channel)

# ----------------------------------------------------------------------------

# todo:  look up current channel for many clients at the same time
#
def current_channel(client):
   return channel_collection.set_of(client)


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
         if isinstance(message['data'], basestring):
            event, mesg = message['data'].split(';', 1)
            # print event, mesg
            yield 'event: {0}\ndata: {1}\n\n'.format(event, mesg)

   return Response(event_stream(), mimetype="text/event-stream")

# ----------------------------------------------------------------------------
