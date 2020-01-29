import os
import gc
import functools
import base64
from datetime import datetime

import simplejson as json
import psaw
import requests

from flask import Flask
from flask import request, jsonify, abort

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

firebase_admin.initialize_app(credentials.ApplicationDefault())
reddit = psaw.PushshiftAPI()
db = firestore.client()
session = requests.Session()
app = Flask(__name__)


@app.route('/r/<subreddit>')
def run(subreddit):
  before = request.args.get('before', type=int)

  submissions = reddit.search_submissions(
    before=before,
    subreddit=subreddit,
    limit=500,
    filter=[
      'id',
      'over_18',
      'score',
      'selftext',
      'title',
    ],
  )

  f1 = lambda p: p.d_
  f2 = lambda q: {k: v for k, v in q.items() if k != 'created'}
  fn = lambda r: functools.reduce(lambda v, f: f(v), (f1, f2), r)

  unfiltered = [fn(d) for d in submissions]
  garbage = ['http', '[removed]', 'www']
  filters = [
    lambda d: bool(d.get('selftext')),
    lambda d: all(r not in d['selftext'] for r in garbage),
  ]

  results = filter(lambda v: all([f(v) for f in filters]), unfiltered)

  batch = db.batch()
  for result in results:
    batch.set(db.document(f'{subreddit}/{result["id"]}'), result)
  batch.commit()

  return jsonify(epoch=locals()
    .get('result', {})
    .get('created_utc'))


@app.route('/', methods=['POST'])
def pubsub():
  envelope = request.get_json()
  if not envelope:
    return ('', 400)

  if not isinstance(envelope, dict) or 'message' not in envelope:
    return ('', 400)

  message = envelope['message']

  if not isinstance(message, dict) or 'data' not in message:
    return ('', 400)

  data = base64.b64decode(message['data']).decode('utf-8').strip()
  json.loads(data)

  return ('', 204)


@app.after_request
def after_request_func(response):
  gc.collect()
  return response
