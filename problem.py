import datetime
from config import db, auth, red
from flask import Blueprint, Response, render_template, request, redirect, url_for, flash
from peewee import *
import sse
from student_record import StudentRecord

problem_page = Blueprint('problem_page', __name__, url_prefix='/problem')
drop_tables = False

# ----------------------------------------------------------------------------
class Problem (db.Model):
   created = DateTimeField(default=datetime.datetime.now)
   description = TextField()
   points = IntegerField()

class Tag (db.Model):
   name = CharField()

class ProblemTag (db.Model):
   problem = ForeignKeyField(Problem)
   tag = ForeignKeyField(Tag)

# ----------------------------------------------------------------------------

@problem_page.before_app_first_request
def init():
   red.delete('published-problems')
   if drop_tables:
      print 'problem.py: drop tables'
      Problem.drop_table(fail_silently=True)
      Tag.drop_table(fail_silently=True)
      ProblemTag.drop_table(fail_silently=True)
   else:
      Problem.create_table(fail_silently=True)
      Tag.create_table(fail_silently=True)
      ProblemTag.create_table(fail_silently=True)

# ----------------------------------------------------------------------------

@problem_page.route('/')
@auth.login_required
def index():
   query = ProblemTag.select(ProblemTag, Problem, Tag).join(Problem).switch(ProblemTag).join(Tag)

   items = {}
   for i in query:
      if i.problem.id not in items:
         items[i.problem.id] = []
      items[i.problem.id].append(i)

   published_probs = red.smembers('published-problems')
   published_probs = [int(p) for p in published_probs]
   stats = { pid : (pid in published_probs) for pid in items }

   return render_template('problem/index.html', stats = stats, items=items, sorted=sorted)

# ----------------------------------------------------------------------------

@problem_page.route('/award_brownie/<int:uid>/<int:tid>/<int:chat_id>')
@auth.role_required('teacher')
def award_brownie(uid, tid, chat_id):
   student = StudentRecord(uid)
   student.brownies += 1
   student.save()

   message = {}
   message[uid] = dict(cid=student.id, chat_id=chat_id, brownies=student.brownies,
      total_score=sum(student.scores.values()))

   if int(sse.current_channel(student.id)) == student.id:
      # only update score if teacher is in the student's sandbox; if not, no need to update.
      message[tid] = dict(cid=student.id, brownies=student.brownies,
         total_score=sum(student.scores.values()))

   sse.notify(message, event="update-score")

   return 'A brownie has been awarded to %s.' % student.username

# ----------------------------------------------------------------------------
@problem_page.route('/publish_toggle/<int:pid>')
@auth.role_required('teacher')
def publish_toggle(pid):
   if not red.sismember('published-problems', pid):
      red.sadd('published-problems', pid)
   else:
      red.srem('published-problems', pid)

   all_records = StudentRecord.all_online()
   pids = red.smembers('published-problems')
   pids = sorted(int(p) for p in pids)
   messages = {}
   for k, v in all_records.items():
      messages[k] = dict(cid = sse.current_channel(k), pids = pids)
   sse.notify(messages, event="problems-updated")

   return redirect(url_for('problem_page.index'))

# ----------------------------------------------------------------------------

@problem_page.route('/create', methods=['GET','POST'])
def create():
   tags = Tag.select()
   if request.method == 'POST':
      p = Problem.create(points=request.form['points'],description = request.form['description'])

      for t in request.form.getlist('tags'):
         tag = Tag.get(Tag.id == int(t))
         problem_tag = ProblemTag.create(tag=tag, problem=p)

      return redirect(url_for('problem_page.index'))

   return render_template('problem/create.html', tags=tags)

# ----------------------------------------------------------------------------

@problem_page.route('/edit/<int:pid>', methods=['GET','POST'])
@auth.role_required('teacher')
def edit(pid = None):

   try:
      p = Problem.get(Problem.id == pid)
      tags = Tag.select().join(ProblemTag).join(Problem).where(Problem.id == pid)

   except Problem.DoesNotExist:
      flash('problem %s does not exist' % pid)
      return url_for('problem_page.list')

   if request.method == 'POST':
      p.points = request.form['points']
      p.description = request.form['description']
      p.save()

      old_tag_ids = set(t.id for t in tags)
      new_tag_ids = set( int(i) for i in request.form.getlist('tags') )
      to_remove = list( old_tag_ids - new_tag_ids )
      to_insert = list( new_tag_ids - old_tag_ids )

      if to_remove:
         res = ProblemTag.delete().where(ProblemTag.problem == p.id, ProblemTag.tag << to_remove)
         res.execute()

      for t in to_insert:
         res = ProblemTag.create(problem=p, tag=t)

      return redirect(url_for('problem_page.edit',pid=p.id))

   all_tags = Tag.select()
   return render_template('problem/edit.html', p=p, all_tags=all_tags, tags=tags)

# ----------------------------------------------------------------------------

@problem_page.route('/grade', methods=['POST'])
@auth.role_required('teacher')
def grade():
   uid = int(request.form['uid'])
   tid = int(request.form['tid'])
   pid = int(request.form['pid'])
   score = int(request.form['score'])

   user_record = StudentRecord(uid)
   user_record.scores[pid] = score
   user_record.save()

   message = {}
   m = dict(cid=user_record.id, total_score=sum(user_record.scores.values()), brownies=user_record.brownies)
   message[uid] = m
   message[tid] = m
   sse.notify(message, event="update-score")
   return '<i class="icon-okay"></i>'

# ----------------------------------------------------------------------------

@problem_page.route('/view/<int:pid>/<int:uid>')
@problem_page.route('/view/<int:pid>')
@auth.login_required
def view(pid, uid=None):
   try:
      prob = Problem.get(Problem.id == pid)
   except Problem.DoesNotExist:
      flash('Problem %s does not exist' % pid)
      return redirect(url_for('index.html'))

   if uid is None:
      return render_template('problem/view.modal', prob=prob)

   teacher = auth.get_logged_in_user()
   if teacher.role != 'teacher':
      return render_template('problem/view.modal', prob=prob)

   student = StudentRecord(uid)
   score = student.scores.get(pid, None)

   return render_template('problem/view_grade.modal', prob=prob, teacher=teacher,
      student=student, score=score)

# ----------------------------------------------------------------------------
# Tag management
# ----------------------------------------------------------------------------
@problem_page.route('/edit_tag', methods=['GET','POST'])
@problem_page.route('/edit_tag/<int:tid>', methods=['GET','POST'])
def edit_tag(tid = None):
   if tid is not None:
      mode = 'edit'
      try:
         tag = Tag.get(Tag.id == tid)
      except Tag.DoesNotExist:
         flash('Tag does not exist')
         return redirect(url_for('index'))
   else:
      tag = None
      mode = 'create'

   if request.method == 'POST':
      if tid is None:
         tag = Tag()
         flash('Tag created')
      else:
         flash('Tag updated')
      tag.name = request.form['name']
      tag.save()
      return redirect(url_for('problem_page.tags'))

   return render_template('problem/edit_tag.html', tag=tag)

# ----------------------------------------------------------------------------

@problem_page.route('/tags')
def tags():
   tags = Tag.select()
   return render_template('problem/tags.html', tags=tags)

# ----------------------------------------------------------------------------

@problem_page.route('/problem_tag_list')
def problem_tag_list():
   entries = ProblemTag.select()
   return render_template('/problem/problem_tag_list.html', entries=entries)
# ----------------------------------------------------------------------------
