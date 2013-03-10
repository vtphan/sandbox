
from red import Red, Field

class UserRecord ( Red ):
   score = Field(int, 0)
   brownie = Field(int, 0)
   view_all_boards = Field(bool, False)
   open_board = Field(bool, False)

   def __init__(self, uid):
      super(UserRecord, self).__init__(uid)

   @classmethod
   def get_all(cls):
      things = super(UserRecord, cls).get_all()
      return { int(k) : v for k,v in things.items() }

if __name__ == '__main__':
   for k,v in UserRecord.get_all().items():
      print k,type(k), v
   pass