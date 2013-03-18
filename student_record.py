
from redcord import Redcord, Field

class StudentRecord ( Redcord ):
   score = Field(int, 0)
   brownie = Field(int, 0)
   view_all_boards = Field(bool, False)
   open_board = Field(bool, False)

   def __init__(self, uid):
      super(StudentRecord, self).__init__(uid)

   @classmethod
   def get_all(cls):
      things = super(StudentRecord, cls).get_all()
      return { int(k) : v for k,v in things.items() }


if __name__ == '__main__':
   # for k,v in StudentRecord.get_all().items():
   #    print k,type(k), v.id, type(v.id)
   # x = StudentRecord(3)
   # print x.id, type(x.id), x

   pass