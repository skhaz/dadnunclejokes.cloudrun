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
from google.cloud import pubsub_v1

app = Flask(__name__)
firebase_admin.initialize_app(credentials.ApplicationDefault())
reddit = psaw.PushshiftAPI()
db = firestore.client()
session = requests.Session()
publisher = pubsub_v1.PublisherClient()


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

  unfiltered = [p.d_ for p in submissions]
  garbage = ['', 'http', '[removed]', 'www']
  results = filter(lambda d: d.get('selftext', '') not in garbage, unfiltered)

  batch = db.batch()
  for result in results:
    batch.set(
      db.document(f'{subreddit}/{result["id"]}'), { **result, "translated", False })
  batch.commit()

  return jsonify(timestamp=locals().get('result', {}).get('created_utc'))


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
  payload = json.loads(data)

  timestamp = payload.get('timestamp')
  if not timestamp:
    return ('', 204)

  subreddit = payload['subreddit']
  url = '%s/r/%s' % (os.environ["BASE_URL"], subreddit)
  response = session.get(url, params={'before': timestamp})
  if not response.ok:
    return ('', 503)

  timestamp = response.json()["timestamp"]
  payload = dict(timestamp=timestamp, subreddit=subreddit)
  publisher.publish(
    topic, data=json.dumps(payload).encode('utf-8')).result()

  return ('', 204)


@app.after_request
def after_request_func(response):
  gc.collect()
  return response
