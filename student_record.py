
from redcord import Redcord, Field

class StudentRecord ( Redcord ):
   scores = Field(dict, {})
   brownies = Field(int, 0)
   view_all_boards = Field(bool, False)
   open_board = Field(bool, False)
   online = Field(bool, False)

   def __init__(self, uid):
      super(StudentRecord, self).__init__(uid)

   @classmethod
   def get_all(cls):
      things = super(StudentRecord, cls).get_all()
      return { int(k) : v for k,v in things.items() }

   @classmethod
   def all_online(cls):
      things = super(StudentRecord, cls).get_all()
      return { int(k) : v for k,v in things.items() if v.online==True }

if __name__ == '__main__':
   for k,v in StudentRecord.get_all().items():
      print k, v
   # a = StudentRecord(3)
   # a.scores[3] = 30
   # a.save()
   pass
