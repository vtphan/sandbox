import datetime
from config import db, auth, red
from flask import Blueprint, Response, render_template, request, redirect, url_for, flash
from peewee import *
import sse
from student_record import StudentRecord

problem_set_page = Blueprint('problem_set', __name__, url_prefix='/problem_set')
drop_tables = False

# ----------------------------------------------------------------------------
class ProblemSet (db.Model):
   created = DateTimeField(default=datetime.datetime.now)

# ----------------------------------------------------------------------------
class Problem (db.Model):
   description = TextField()
   points = IntegerField()
   viewable = BooleanField(default=False)
   problem_set = ForeignKeyField(ProblemSet, related_name='problems')

# ----------------------------------------------------------------------------

@problem_set_page.before_app_first_request
def init():
   if drop_tables:
      ProblemSet.drop_table(fail_silently=True)
      Problem.drop_table(fail_silently=True)
   else:
      ProblemSet.create_table(fail_silently=True)
      Problem.create_table(fail_silently=True)

# ----------------------------------------------------------------------------
@problem_set_page.route('/list', methods=['GET','POST'])
def list():
   if request.method == 'POST':
      ps = ProblemSet.create()
      return redirect( url_for('problem_set.edit', pid=ps.id) )
   creatable = auth.get_logged_in_user().role == 'teacher'
   return render_template('problem_set/list.html', creatable=creatable,
      ps = ProblemSet.select().order_by(ProblemSet.id) )

# ----------------------------------------------------------------------------
@problem_set_page.route('/<int:pid>')
@auth.login_required
def index(pid):
   try:
      ps = ProblemSet.get(ProblemSet.id == pid)
   except ProblemSet.DoesNotExist:
      flash('problem set %s does not exist' % pid)
      return render_template('index.html')

   problems = Problem.select().annotate(ProblemSet).where(ProblemSet.id == pid).order_by(Problem.id.asc())

   editable = auth.get_logged_in_user().role == 'teacher'
   return render_template('problem_set/index.html', ps=ps, problems=problems, editable=editable)

# ----------------------------------------------------------------------------

@problem_set_page.route('/edit/<int:pid>', methods=['GET','POST'])
@auth.role_required('teacher')
def edit(pid):
   try:
      ps = ProblemSet.get(ProblemSet.id == pid)
   except ProblemSet.DoesNotExist:
      flash('problem set %s does not exist' % pid)
      return render_template('index.html')

   problems = Problem.select().annotate(ProblemSet).where(ProblemSet.id == pid).order_by(Problem.id.asc())

   if request.method == 'POST':
      if 'publish' in request.form:
         pids = [p.id for p in problems if p.viewable]
         if pids:
            pipe = red.pipeline()
            pipe.delete('published-problem-set')
            pipe.sadd('published-problem-set', *pids)
            pipe.execute()

            all_records = StudentRecord.all_online()
            messages = {}
            for k, v in all_records.items():
               messages[k] = dict(cid = sse.current_channel(k), pids = pids)
            sse.notify(messages, event="published-problem-set")
            flash('Problem set published.')

      else:
         problem = Problem()
         problem.points = request.form['points']
         problem.description = request.form['description']
         problem.problem_set = request.form['problemset']
         problem.save()
         return redirect( url_for('problem_set.edit', pid=ps.id) )

   return render_template('problem_set/edit.html', ps=ps, problems=problems)

# ----------------------------------------------------------------------------

@problem_set_page.route('/edit_problem/<int:pid>', methods=['GET','POST'])
@auth.role_required('teacher')
def edit_problem(pid):
   try:
      prob = Problem.get(Problem.id == pid)
   except Problem.DoesNotExist:
      flash('problem %s does not exist' % pid)
      return render_template('index.html')

   if request.method == 'POST':
      psid = prob.problem_set.id
      if 'delete' in request.form:
         prob.delete_instance()
         flash('Problem %s is deleted' % prob.id)
         return redirect(url_for('problem_set.edit', pid=psid))
      else:
         prob.points = request.form['points']
         prob.description = request.form['description']
         prob.viewable = 'viewable' in request.form
         prob.save()
         return redirect(url_for('problem_set.edit', pid=psid))

   return render_template('problem_set/edit_problem.html', prob=prob)
# ----------------------------------------------------------------------------

@problem_set_page.route('/view_problem/<int:pid>/<int:uid>')
@auth.login_required
def view_problem(pid, uid):
   try:
      prob = Problem.get(Problem.id == pid)
   except Problem.DoesNotExist:
      flash('Problem %s does not exist' % pid)
      return redirect(url_for('index.html'))

   user = auth.get_logged_in_user()
   if user.role != 'teacher' and prob.viewable == False:
      return 'This problem is not ready yet.'

   student_record = StudentRecord(int(uid))
   score = student_record.scores.get(pid, None)

   view_score = score is not None and (uid==user.id or user.role=='teacher')
   gradable  = (user.role == 'teacher') and (uid != user.id)
   return render_template('problem_set/view_problem.modal', pid=pid, uid=uid,
      prob=prob, score=score, view_score=view_score, gradable=gradable)

# ----------------------------------------------------------------------------
@problem_set_page.route('/grade_problem/<int:pid>/<int:uid>', methods=['GET','POST'])
@auth.role_required('teacher')
def grade_problem(pid, uid):
   try:
      prob = Problem.get(Problem.id == pid)
   except Problem.DoesNotExist:
      flash('Problem %s does not exist' % pid)
      return redirect(url_for('index.html'))

   try:
      user = auth.User.get(auth.User.id == uid)
   except auth.User.DoesNotExist:
      flash('User %s does not exist' % uid)
      return redirect(url_for('index.html'))

   teacher = auth.get_logged_in_user()
   user_record = StudentRecord(int(uid))
   score = user_record.scores.get(pid, None)

   if request.method == 'POST':
      user_record.scores[pid] = int(request.form['score'])
      user_record.save()
      message = {}
      m = dict(cid=user_record.id, total_score=sum(user_record.scores.values()), brownies=user_record.brownies)
      message[user_record.id] = m
      message[teacher.id] = m
      sse.notify(message, event="update-score")
      flash('Score updated for %s' % user.username)
      return redirect(url_for('problem_set.grade_problem', pid=pid, uid=uid))

   return render_template('problem_set/grade_problem.html', user=user, prob=prob, score=score)

# ----------------------------------------------------------------------------


