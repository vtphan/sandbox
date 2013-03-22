
from redcord import Redcord, Field

class StudentRecord ( Redcord ):
   username = Field(str)
   scores = Field(dict, {})
   brownies = Field(int, 0)
   open_board = Field(bool, False)
   online = Field(bool, False)
   is_teacher = Field(bool, False)

   def __init__(self, uid):
      super(StudentRecord, self).__init__(uid)

   @classmethod
   def get_all(cls, f = lambda x: True):
      things = super(StudentRecord, cls).get_all()
      return { int(k) : v for k,v in things.items() if f(v)}

   @classmethod
   def all_online(cls):
      return cls.get_all( lambda v: v.online==True )


StudentRecord.id_type = int

if __name__ == '__main__':
   for k,v in StudentRecord.get_all().items():
      print k, v, type(k)
   pass
