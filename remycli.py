import remy
from remy.remarkable.metadata import *
from remy.remarkable.filesource import LocalFileSource

import os

# from fuzzywuzzy import process
# highest = process.extractOne(str2Match,strOptions)


def filter_by_field(f, v, docs):
  return filter(lambda k: docs[k][f] == v, docs)


def list_folder(docs, uid='', exact=True):
  if not exact:
    uid = docs.matchId(uid)

  if not docs.isFolder(uid):
    print("NOT A FOLDER!")
    return

  folder = docs.get(uid)
  print("FOLDERS")
  for k in folder.folders:
    print('  {0:<20} {1}'.format(docs.get(k).name(), k))

  print("FILES")
  for k in folder.files:
    print('  {0:<20} {1}'.format(docs.get(k).name(), k))

def list_path(docs, path=''):
  uid = docs.uidFromPath(path)
  if uid:
    if not docs.isFolder(uid):
      print("The path is the document with id '{}'.".format(uid))
    else:
      list_folder(docs, uid)
  else:
    print("Not found!")


def list_trash(docs):
  folders = []
  files = []
  lw = 20
  for uid in docs.trash:
    p = docs.pathOf(uid,trashToo=True)
    if p is None:
      p = "UNKNOWN"
    else:
      p = '/' + ('/'.join(p))
    lw = max(lw,len(p))
    if docs.get(uid).type == FOLDER_TYPE:
      folders.append((uid, p))
    elif docs.get(uid).type == DOCUMENT_TYPE:
      files.append((uid, p))

  print(lw)
  print("FOLDERS")
  for k, p in folders:
    print(('  {path}/{visibleName:<'+str(lw+2)+'} {uid}').format(path=p,name=docs.get(k).name(),uid=k))

  print("FILES")
  for k, p in files:
    print(('  {path}/{visibleName:<'+str(lw+2)+'} {uid}').format(path=p,name=docs.get(k).name(),uid=k))

_test_pwd = None

def load(where=None, templ=None):
  global _test_pwd
  if where is None:
    where = os.environ.get('REMYCLI_DOCS','.')
  if templ is None:
    templ = os.environ.get('REMYCLI_TEMPL', '.')
  docs = RemarkableIndex(LocalFileSource("Backup", where, templ))
  _test_pwd = [ROOT_ID, docs]
  list_folder(docs)
  return docs

def ls(path=None):
  uid, docs = _test_pwd
  if path:
    uid = docs.uidFromPath(path, start=uid, delim="/")
  list_folder(docs, uid)

def pwd():
  uid, docs = _test_pwd
  print(docs.nameOf(uid), uid)

def cd(path):
  global _test_pwd
  uid, docs = _test_pwd
  f = docs.uidFromPath(path, start=uid, delim="/")
  if f is None:
    print("Path not found!")
  elif docs.isFolder(f):
    _test_pwd[0] = f
    list_folder(docs, f)
  else:
    print("Path points to a file %s!" % f)


