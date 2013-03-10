'''
Red is a redis object modeler.  A Red object has attributes of type Field.
These attributes will be saved to redis.
These attributes are "type safe": types other than int, float, string are
automatically cPickled.

Example:
   import uuid
   class Record (Red):
      name = Field(str)
      score = Field(int, default=0)
      assist = Field(int, default=0)
      comments = Field(str)
      codes = Field(str)
      session = Field(str)

      # email is the key of Record
      def __init__(self, email):
         super(Record, self).__init__(email)
         self.session = str(uuid.uuid4())

'''
import redis
import cPickle

#
# ----------------------------------------------------------------------------
#
class Field (object):
   def __init__(self, _type=str, default=''):
      self.type = _type
      self.default = default
      self.name = None


   def __get__(self, instance, owner):
      return getattr(instance, self.name)

   def __set__(self, instance, value, flag=True):
      setattr(instance, self.name, value)

#
# ----------------------------------------------------------------------------
# For each field, there is an attribute named:  field__
#
class MetaRed (type):
   def __new__(meta, name, bases, dct):
      if bases[0].__name__ == 'Red':
         #
         # Note: these lists and dicts are shared by all Red instances
         #
         dct['__fields__'] = []
         dct['__field_types__'] = {}
         for a,o in dct.items():
            if isinstance(o, Field):
               field_name = a + '__'
               dct[field_name] = o.default
               dct['__fields__'].append(a)
               dct['__field_types__'][a] = o.type
               dct['__key_prefix__'] = name + ':'
               o.name = field_name

      return type.__new__(meta, name, bases, dct)


#
# ----------------------------------------------------------------------------
# A field is store in __fields__.  Its converter is stored in __field_types__
#
class Red (object):
   __metaclass__ = MetaRed
   conn = redis.StrictRedis(host='localhost', port=6379, db=1)
   pipe = conn.pipeline()

   def __init__(self, _id):
      self.id = _id
      self.__id = self.__key_prefix__ + str(_id)
      self.initialize()

   def initialize(self):
      current = self.conn.hgetall(self.__id)
      for k in set(current.keys()) & set(self.__fields__):
         value = current[k]
         _type = self.__field_types__[k]
         if value != '':
            if _type == bool:
               value = True if value=='True' else False
            elif issubclass(_type, (int,float)):
               value = _type(value)
            elif not issubclass(_type, basestring):
               value = cPickle.loads(value)
         setattr(self, k+'__', value)

   def save(self):
      v = { a:getattr(self,a) if \
         issubclass(self.__field_types__[a], (basestring,int,float,bool)) else \
         cPickle.dumps(getattr(self,a), 2) for a in self.__fields__ }
      self.conn.hmset(self.__id, v)

   def __repr__(self):
      return str( {a:getattr(self,a) for a in self.__fields__} )

   def as_dict(self):
      return { a:getattr(self,a) for a in self.__fields__ }

   @classmethod
   def remove(cls, key):
      return cls.conn.execute_command('del', cls.__key_prefix__ + str(key))

   @classmethod
   def get_all(cls):
      keys = cls.keys()
      items = {}
      for k in keys:
         r = cls(k)
         items[r.id] = r
      return items

   @classmethod
   def keys(cls):
      L = len(cls.__key_prefix__)
      res = cls.conn.execute_command('keys', cls.__key_prefix__ + '*')
      return (k[L:] for k in res)

   @classmethod
   def raw_keys(cls):
      res = cls.conn.execute_command('keys', cls.__key_prefix__ + '*')
      return res

   # @classmethod
   # def values(cls):
   #    keys = cls.raw_keys()
   #    return (cls.conn.hgetall(k) for k in keys)

   @classmethod
   def incr(cls, key, field, val=1):
      _type = cls.__field_types__.get(field, None)
      key = cls.__key_prefix__ + key
      if _type == int:
         return cls.conn.execute_command('hincrby', key, field, val)
      return None

   @classmethod
   def execute(cls, command, *args):
      return cls.conn.execute_command(command, *args)

   def _sync_fields(self):
      current = self.conn.hgetall(self.__id)
      old_keys = set(current.keys()) - set(self.__fields__)
      if old_keys:
         self.conn.hdel(self.__id, *old_keys)

#
# ----------------------------------------------------------------------------
#
