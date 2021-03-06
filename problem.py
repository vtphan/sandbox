import datetime
from config import db, auth, red
from flask import Blueprint, Response, render_template, request, redirect, url_for, flash
from peewee import *
import sse
from student_record import StudentRecord

problem = Blueprint('problem', __name__, url_prefix='/problem')
drop_tables = False

# ----------------------------------------------------------------------------
class Problem (db.Model):
   created = DateTimeField(default=datetime.datetime.now)
   description = TextField()
   points = IntegerField()

class Tag (db.Model):
   name = CharField()

class ProblemTag (db.Model):
   problem = ForeignKeyField(Problem, related_name='problemtags')
   tag = ForeignKeyField(Tag, related_name='problemtags')

class Score (db.Model):
   problem = ForeignKeyField(Problem)
   user = ForeignKeyField(auth.User)
   points = IntegerField()

class Brownie (db.Model):
   user = ForeignKeyField(auth.User)
   points = IntegerField()

# ----------------------------------------------------------------------------

@problem.before_app_first_request
def init():
   if drop_tables:
      print 'problem.py: drop tables'
      Problem.drop_table(fail_silently=True)
      Tag.drop_table(fail_silently=True)
      ProblemTag.drop_table(fail_silently=True)
      Score.drop_table(fail_silently=True)
      Brownie.drop_table(fail_silently=True)
   else:
      Problem.create_table(fail_silently=True)
      Tag.create_table(fail_silently=True)
      ProblemTag.create_table(fail_silently=True)
      Score.create_table(fail_silently=True)
      Brownie.create_table(fail_silently=True)

# ----------------------------------------------------------------------------

@problem.route('/')
@auth.role_required('teacher')
def index():
   query = Problem.select(Problem).join(ProblemTag,JOIN_LEFT_OUTER) \
      .join(Tag,JOIN_LEFT_OUTER).distinct().order_by(Problem.id.desc())
   probs = query.execute()

   published_probs = [ int(p) for p in red.smembers('published-problems') ]
   stats = { p.id : (p.id in published_probs) for p in probs }
   tags = Tag.select()

   return render_template('problem/index.html', stats=stats, probs=probs, tags=tags)

# ----------------------------------------------------------------------------

@problem.route('/create', methods=['GET','POST'])
@auth.role_required('teacher')
def create():
   tags = Tag.select()
   if request.method == 'POST':
      p = Problem.create(points=request.form['points'],description = request.form['description'])

      for t in request.form.getlist('tags'):
         tag = Tag.get(Tag.id == int(t))
         problem_tag = ProblemTag.create(tag=tag, problem=p)

      return redirect(url_for('problem.index'))

   return render_template('problem/create.html', tags=tags)

# ----------------------------------------------------------------------------

@problem.route('/edit/<int:pid>', methods=['GET','POST'])
@auth.role_required('teacher')
def edit(pid = None):
   try:
      p = Problem.get(Problem.id == pid)
      tags = Tag.select().join(ProblemTag).join(Problem).where(Problem.id == pid)

   except Problem.DoesNotExist:
      flash('problem %s does not exist' % pid)
      return url_for('problem.list')

   if request.method == 'POST':
      if 'delete' in request.form:
         ProblemTag.delete().where(ProblemTag.problem == p).execute()
         p.delete_instance()
         return redirect(url_for('problem.index'))


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

      return redirect(url_for('problem.edit',pid=p.id))

   all_tags = Tag.select()
   return render_template('problem/edit.html', p=p, all_tags=all_tags, tags=tags)

# ----------------------------------------------------------------------------

@problem.route('/view/<int:pid>/<int:uid>')
@problem.route('/view/<int:pid>')
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

@problem.route('/publish_toggle/<int:pid>')
@auth.role_required('teacher')
def publish_toggle(pid):
   if not red.sismember('published-problems', pid):
      red.sadd('published-problems', pid)
   else:
      red.srem('published-problems', pid)

   all_records = StudentRecord.online_students()
   pids = sorted(int(p) for p in red.smembers('published-problems'))
   messages = {}
   for k, v in all_records.items():
      uid = sse.current_channel(k) if v.is_teacher else k
      scores = [ [pid, all_records[uid].scores.get(pid,0)] for pid in pids ]
      messages[k] = dict(cid = uid, scores=scores)
   sse.notify(messages, event="problems-updated")

   return redirect(url_for('problem.index'))

# ----------------------------------------------------------------------------

@problem.route('/award_brownie/<int:uid>/<int:tid>/<int:chat_id>')
@auth.role_required('teacher')
def award_brownie(uid, tid, chat_id):
   student = StudentRecord(uid)
   student.brownies += 1
   student.save()

   message = dict(cid=student.id, chat_id=chat_id, brownies=student.brownies)
   sse.notify( {uid: message, tid : message}, event="brownie-updated")

   q = Brownie.update(points = Brownie.points +1).where(Brownie.user == uid)
   if q.execute() == 0:
      q = Brownie.create(user=uid, points=1)

   return 'A brownie has been awarded to %s.' % student.username

# ----------------------------------------------------------------------------

@problem.route('/grade', methods=['POST'])
@auth.role_required('teacher')
def grade():
   uid = int(request.form['uid'])
   tid = int(request.form['tid'])
   pid = int(request.form['pid'])
   score = int(request.form['score'])

   # Store in redis
   user_record = StudentRecord(uid)
   user_record.scores[pid] = score
   user_record.save()

   pids = sorted(int(i) for i in red.smembers('published-problems'))
   scores = [ [p, user_record.scores.get(p,0)] for p in pids ]
   message = dict(cid=user_record.id, scores=scores, pid=pid, score=score)

   sse.notify({uid:message, tid:message}, event="scores-updated")

   # Store in database
   q = Score.update(points=score).where(Score.problem==pid, Score.user==uid)
   if q.execute() == 0:
      q = Score.create(problem=pid, user=uid, points=score)

   return '<i class="icon-okay"></i>'


# ----------------------------------------------------------------------------

@problem.route('/grade/history')
@problem.route('/grade/history/<int:uid>')
@auth.login_required
def grade_history(uid = None):
   logged_in_user = auth.get_logged_in_user()
   if uid is not None:
      if logged_in_user.role != 'teacher' and logged_in_user.id != uid:
         return 'not allowed'
   else:
      uid = logged_in_user.id

   student = StudentRecord(uid)

   try:
      scores = Score.select().where(Score.user == uid)
   except Score.DoesNotExist:
      scores = []

   try:
      brownie = Brownie.get(Brownie.user == uid)
   except Brownie.DoesNotExist:
      brownie = None

   published_pids = red.smembers('published-problems')
   published_pids = sorted(int(p) for p in published_pids)

   return render_template('problem/grade_history.html', scores=scores, brownie=brownie,
      student=student, published_pids=published_pids)

# ----------------------------------------------------------------------------
# Tag management
# ----------------------------------------------------------------------------
@problem.route('/edit_tag', methods=['GET','POST'])
@problem.route('/edit_tag/<int:tid>', methods=['GET','POST'])
@auth.role_required('teacher')
def edit_tag(tid = None):
   if tid is not None:
      try:
         tag = Tag.get(Tag.id == tid)
      except Tag.DoesNotExist:
         flash('Tag does not exist')
         return redirect(url_for('index'))
   else:
      tag = None

   if request.method == 'POST':
      if tid is None:
         tag = Tag()
         flash('Tag created')
      else:
         flash('Tag updated')
         if 'delete' in request.form:
            ProblemTag.delete().where(ProblemTag.tag == tag).execute()
            tag.delete_instance()
            return redirect(url_for('problem.index'))

      tag.name = request.form['name']
      tag.save()
      return redirect(url_for('problem.index'))

   return render_template('problem/edit_tag.html', tag=tag)

# ----------------------------------------------------------------------------

@problem.route('/problem_tag_list')
@auth.role_required('teacher')
def problem_tag_list():
   entries = ProblemTag.select()
   return render_template('/problem/problem_tag_list.html', entries=entries)
# ----------------------------------------------------------------------------
