from flask import Flask
from flask_peewee.db import Database
from peewee import *
from auth import Auth
import redis

DATABASE = { 'name': 'sandbox.db', 'engine': 'peewee.SqliteDatabase' }
DEBUG = True
SECRET_KEY = 'ssshhhh'

app = Flask(__name__)
app.config.from_object(__name__)

db = Database(app)
auth = Auth(app, db)
red = redis.StrictRedis()
