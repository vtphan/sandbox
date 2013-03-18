'''
Maintain a collection of items partitioned into many sets.
   insert - insert item(s) into a set.
   remove - remove an item from a set.
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
   def remove(self, item):
      s = self.set_of(item)
      if s is not None:
         self.remove_from(s, item)

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
   print c.get_all()
   c.insert(5, 5, 10, 20)
   print c.get_all()
