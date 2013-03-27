from flask import render_template, request, redirect, url_for, flash, Blueprint
from config import app, db, auth, red
from student_record import StudentRecord
import sse

user_page = Blueprint('user_page', __name__, url_prefix='/user', template_folder='templates/user')

# ----------------------------------------------------------------------------
@user_page.before_app_first_request
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
@user_page.route('/logout')
@auth.login_required
def logout():
   user = auth.get_logged_in_user()
   auth.logout_user(user)
   user_record = StudentRecord(user.id)
   user_record.open_board = False
   user_record.online = False
   user_record.save()
   all_records = StudentRecord.all_online()
   listening_clients = sse.listening_clients(user.id)

   # Turn off menu/tabs of all listeners and tell them to go home
   mesg = {}
   for cid in all_records:
      mesg[cid] = dict(cid=user.id)
      if cid in listening_clients or cid==user.id:
         mesg[cid].update(home_cid = cid)
         sse.listen_to(cid, cid)
   sse.notify(mesg, event="log-out")
   sse.close(user_record.id)

   return redirect(url_for('index'))

# ----------------------------------------------------------------------------
@user_page.route('/list', methods=['GET','POST'])
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
      return redirect(url_for('user_page.list'))
   return render_template('user/list.html', users=auth.User.select())

# ----------------------------------------------------------------------------
@user_page.route('/edit', methods=['GET','POST'])
@user_page.route('/edit/<int:uid>', methods=['GET','POST'])
@auth.login_required
def edit(uid=None):
   redirect_to_index = uid is None
   cur_user = auth.get_logged_in_user()
   uid = cur_user.id if uid is None else uid
   if cur_user.role!='teacher' and cur_user.id!=uid:
      flash('you do not have permission')
      return redirect(url_for('index'))

   user = cur_user if cur_user.id==uid else auth.User.get(auth.User.id==uid)

   if request.method == 'POST':
      if 'delete' in request.form:
         user.delete_instance()
         flash('User %s is deleted' % user.username)
         return redirect(url_for('user_page.list'))
      else:
         print request.form, 'username' in request.form
         if 'username' in request.form:
            user.username = request.form['username']
         user.active = 'active' in request.form
         user.email = request.form['email']
         user.role = request.form['role']
         if request.form['new_password']:
            user.set_password(request.form['new_password'])
         user.save()
         flash('Information updated')
         if redirect_to_index:
            return redirect(url_for('index'))
         return redirect(url_for('user_page.list'))
   return render_template('user/edit.html', cur_user=cur_user, user=user)

# ----------------------------------------------------------------------------
