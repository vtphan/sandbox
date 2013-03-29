from config import app, auth, red
from flask import render_template, redirect, url_for
from user import user_page
from sse import sse_bp
from sandbox import sandbox_bp
from problem import problem_page
from student_record import StudentRecord

# ----------------------------------------------------------------------------
@app.route('/')
def index():
	user = auth.get_logged_in_user()
	if not user:
		return redirect(url_for('auth.login'))
	return render_template('index.html', user=user)

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
   user_record.online = True
   if logged_in_user.role == 'teacher':
      user_record.open_board = True
      user_record.is_teacher = True
   user_record.save()

# ----------------------------------------------------------------------------

app.register_blueprint(sse_bp)
app.register_blueprint(sandbox_bp)
app.register_blueprint(user_page)
app.register_blueprint(problem_page)

if __name__ == "__main__":
	app.run(port=8000)