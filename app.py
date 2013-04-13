from config import app, auth, red
from flask import render_template, redirect, url_for
from user import user
from sse import sse
from sandbox import sandbox
from problem import problem
from student_record import StudentRecord

# ----------------------------------------------------------------------------
@app.route('/admin')
@auth.role_required('teacher')
def admin():
   user = auth.get_logged_in_user()
   num_online = len(StudentRecord.online_students())
   if not user:
      return redirect(url_for('auth.login'))
   return render_template('admin.html', user=user, num_online=num_online)

# ----------------------------------------------------------------------------
@app.route('/')
def index():
   user = auth.get_logged_in_user()
   if not user:
      return redirect( url_for('auth.login') )
   return redirect( url_for('sandbox.index') )

# ----------------------------------------------------------------------------

@app.before_first_request
def init():
   red.delete('published-problems')
   red.set('chat-count', 0)
   # red.flushdb()

# ----------------------------------------------------------------------------

@auth.after_login
def init_user():
   logged_in_user = auth.get_logged_in_user()
   user_record = StudentRecord(logged_in_user.id)
   user_record.username = logged_in_user.username
   if logged_in_user.role == 'teacher':
      user_record.open_board = True
      user_record.is_teacher = True
   user_record.save()

# ----------------------------------------------------------------------------

app.register_blueprint(sse)
app.register_blueprint(sandbox)
app.register_blueprint(user)
app.register_blueprint(problem)

if __name__ == "__main__":
	app.run(port=8000)