'''
Two data structures:

rset-<prefix>- is a redis hash.  rset-<prefix>- [i] tells which channel item i is currently in.
rset-<prefix>-j is a redis set.  rset-<prefix>-j tells which items are currently listening to channel j.
'''
import redis

class Collection (object):
   r = redis.StrictRedis()

   def __init__(self, name, type_of_sid = int, type_of_items = int):
      self.name = name
      self.prefix = 'rset-%s-' % name
      self.type_of_sid = type_of_sid
      self.type_of_items = type_of_items

   # ------------------------------------------------------------------------
   # Insert into set sid items.
   # If an item exists in another set, it is move to set sid.
   # redis automatically removes empty sets.
   #
   # ------------------------------------------------------------------------
   def insert(self, sid, *items):
      pipe = self.r.pipeline()
      for i in items:
         set_of_i = self.set_of(i)
         if set_of_i is None:
            pipe.sadd(self.prefix+str(sid), i)
         else:
            pipe.smove(self.prefix+str(set_of_i), self.prefix+str(sid), i)
         pipe.hset(self.prefix, i, sid)
      pipe.execute()

   # ------------------------------------------------------------------------
   def set_of(self, item):
      res = self.r.hget(self.prefix, item)
      return None if res is None else self.type_of_sid(res)

   # ------------------------------------------------------------------------
   def remove_from(self, sid, item):
      pipe = self.r.pipeline()
      pipe.hdel(self.prefix, item)
      pipe.srem(self.prefix + str(sid), item)
      pipe.execute()

   # ------------------------------------------------------------------------
   def remove_item(self, item):
      s = self.set_of(item)
      if s is not None:
         self.remove_from(s, item)

   # ------------------------------------------------------------------------
   def remove_channel(self, channel):
      self.r.delete(self.prefix + str(channel))

   # ------------------------------------------------------------------------
   def members(self, sid):
      res = self.r.smembers(self.prefix + str(sid))
      return set(self.type_of_items(i) for i in res)

   # ------------------------------------------------------------------------
   def keys(self):
      res = self.r.hvals(self.prefix)
      return set(self.type_of_sid(i) for i in res)

   # ------------------------------------------------------------------------
   def get_all(self):
      keys = self.keys()
      pipe = self.r.pipeline()
      for k in keys:
         pipe.smembers(self.prefix + str(k))
      res = pipe.execute()
      return { k : set(self.type_of_items(j) for j in res[i]) for i,k in enumerate(keys) }

   # ------------------------------------------------------------------------

if __name__ == '__main__':
   c = Collection('test')
   # print c.members(1), c.members(10)
   # c.insert(3, 7, 6, 30, 15)
   # c.insert(6, 1,2,3,4,5)
   # c.insert(5, 5,9,10,11,12)
   # c.insert(5, 6)
   print c.get_all()
