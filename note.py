import datetime
from flask import Flask, request, flash, redirect, url_for, render_template
from flask_peewee.auth import Auth
from flask_peewee.db import Database
from peewee import *

# configure our database
DATABASE = { 'name': 'example.db', 'engine': 'peewee.SqliteDatabase' }
DEBUG = True
SECRET_KEY = 'ssshhhh'

app = Flask(__name__)
app.config.from_object(__name__)
db = Database(app)

auth = Auth(app, db)

@app.route('/add-user', methods=['GET', 'POST'])
def add_user():
   if request.method == 'POST':
      user = auth.User(username=request.form['username'], email=request.form['email'])
      user.active = True
      user.set_password(request.form['password'])
      user.save()
      flash('user created')
   return render_template('add_user.html')

@app.route('/users')
def users():
   u = auth.User.select()
   return render_template('users.html', u=u)

@app.route('/private')
@auth.login_required
def private():
   return 'this is a private area.  Log in is required'

@app.route('/logout')
@auth.login_required
def logout():
   user = auth.get_logged_in_user()
   auth.logout_user(user)
   flash('log out')
   return redirect(url_for('add_user'))

if __name__ == '__main__':
   auth.User.create_table(fail_silently=True)
   app.debug=True
   app.run()