import datetime
from config import db, auth
from flask import Blueprint, Response, render_template, request, redirect, url_for, flash
from peewee import *

problem_set_page = Blueprint('problem_set', __name__, url_prefix='/problem_set')

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
   # ProblemSet.drop_table(fail_silently=True)
   # Problem.drop_table(fail_silently=True)
   ProblemSet.create_table(fail_silently=True)
   Problem.create_table(fail_silently=True)


# ----------------------------------------------------------------------------
@problem_set_page.route('/list', methods=['GET','POST'])
def list():
   if request.method == 'POST':
      ps = ProblemSet.create()
      return redirect( url_for('problem_set.edit', pid=ps.id) )

   creatable = auth.get_logged_in_user().role == 'teacher'
   return render_template('problem_set/list.html', ps = ProblemSet.select().order_by(ProblemSet.id) )

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
         print 'here'
         return redirect(url_for('problem_set.edit', pid=psid))

   return render_template('problem_set/edit_problem.html', prob=prob)
# ----------------------------------------------------------------------------

@problem_set_page.route('/view_problem/<int:pid>')
@auth.login_required
def view_problem(pid):
   try:
      prob = Problem.get(Problem.id == pid)
   except Problem.DoesNotExist:
      flash('Problem %s does not exist' % pid)
      return redirect(url_for('index.html'))
   user = auth.get_logged_in_user()
   if user.role != 'teacher' and prob.viewable == False:
      return 'This problem is not ready yet.'

   return render_template('problem_set/view_problem.html', prob=prob)
# ----------------------------------------------------------------------------
