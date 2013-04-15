from flask import render_template, request, redirect, url_for, flash, Blueprint
from config import app, db, auth, red
from student_record import StudentRecord
import sse

user = Blueprint('user', __name__, url_prefix='/user', template_folder='templates/user')

# ----------------------------------------------------------------------------
@user.before_app_first_request
def init_user_table():
   auth.User.create_table(fail_silently=True)
   if auth.User.select().count() == 0:
      admin = auth.User(username='Teacher',email='admin@localhost')
      admin.active = True
      admin.admin = True
      admin.role = 'teacher'
      admin.set_password('password')
      admin.save()

# ----------------------------------------------------------------------------
def logout_and_cleanup(uid=None, next_url=None):
   online_students = StudentRecord.online_students()

   if uid is None:
      user = auth.get_logged_in_user()
      auth.logout_user(user)
   else:
      user = auth.User.get(auth.User.id == uid)
      auth.logout_user(user, self_logout=False)

   user_record = StudentRecord(user.id)
   user_record.open_board = False
   user_record.online = False
   user_record.save()

   listening_clients = sse.listening_clients(user.id)

   # Turn off menu/tabs of all listeners and tell them to go home
   mesg = {}
   for cid in online_students:
      mesg[cid] = dict(cid=user.id)
      if cid in listening_clients or cid==user.id:
         mesg[cid].update(home_cid = cid)
         sse.listen_to(cid, cid)
   sse.notify(mesg, event="log-out")
   sse.close(user_record.id)

   return redirect( next_url or url_for('index') )

# ----------------------------------------------------------------------------

@user.route('/logout')
@auth.login_required
def logout():
   return logout_and_cleanup()

# ----------------------------------------------------------------------------
@user.route('/logout_user/<int:uid>')
@auth.role_required('teacher')
def logout_user(uid):
   user = auth.get_logged_in_user()
   if user.id == uid:
      return logout_and_cleanup()
   else:
      return logout_and_cleanup(uid, url_for('user.online'))

# ----------------------------------------------------------------------------
@user.route('/online')
@auth.role_required('teacher')
def online():
   students = StudentRecord.online_students()
   return render_template('user/online.html', students=students)

# ----------------------------------------------------------------------------
@user.route('/list', methods=['GET','POST'])
@auth.role_required('teacher')
def list():
   cur_user = auth.get_logged_in_user()

   if request.method == 'POST':
      user = auth.User(username=request.form['username'])
      user.email = request.form['username'] + '@memphis.edu'
      user.set_password(request.form['username'])
      user.active = True
      user.role = 'student'
      user.save()
      flash('user %d created' % user.id)
      return redirect(url_for('user.list'))
   return render_template('user/list.html', users=auth.User.select())

# ----------------------------------------------------------------------------
@user.route('/edit', methods=['GET','POST'])
@user.route('/edit/<int:uid>', methods=['GET','POST'])
@auth.login_required
def edit(uid=None):
   cur_user = auth.get_logged_in_user()
   uid = cur_user.id if uid is None else uid
   if cur_user.role!='teacher' and cur_user.id!=uid:
      return redirect(url_for('auth.permission_denied'))

   user = cur_user if cur_user.id==uid else auth.User.get(auth.User.id==uid)

   if request.method == 'POST':
      if 'delete' in request.form:
         user.delete_instance()
         flash('User %s is deleted' % user.username)
         return redirect(url_for('user.list'))
      else:
         if 'username' in request.form:
            user.username = request.form['username']
         user.active = 'active' in request.form
         user.email = request.form['email']
         user.role = request.form['role']
         if request.form['new_password']:
            user.set_password(request.form['new_password'])
         user.save()
         flash('Information updated')
         if cur_user.role == 'teacher':
            return redirect(url_for('user.list'))
   return render_template('user/edit.html', cur_user=cur_user, user=user)

# ----------------------------------------------------------------------------
