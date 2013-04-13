
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
   def all_students(cls, f = lambda x: True):
      things = super(StudentRecord, cls).all()
      return { int(k) : v for k,v in things.items() if f(v)}

   @classmethod
   def online_students(cls):
      return cls.all_students( lambda v: v.online==True )

   @classmethod
   def count(cls):
      return len( cls.keys() )

StudentRecord.id_type = int

if __name__ == '__main__':
   for k,v in StudentRecord.all_students().items():
      print k, v
   print StudentRecord.count()