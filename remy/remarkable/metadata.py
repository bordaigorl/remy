#!/usr/bin/env python3
import sys
import os
import json
from itertools import *
from collections import namedtuple
import arrow
import uuid

from remy.remarkable.lines import *
from remy.remarkable.constants import *

# DocIndex = namedtuple('DocIndex', 'metadata tree trash')
FolderNode = namedtuple('FolderNode', 'folders files')

FOLDER_TYPE = "CollectionType"
DOCUMENT_TYPE = "DocumentType"

NOTEBOOK = 1
PDF = 2
EPUB = 4
FOLDER = 8
DELETED_NOTEBOOK = NOTEBOOK << 4
DELETED_PDF = PDF << 4
DELETED_EPUB = EPUB << 4
DELETED_FOLDER = FOLDER << 4

NOTEBOOK = NOTEBOOK | DELETED_NOTEBOOK
PDF = PDF | DELETED_PDF
EPUB = EPUB | DELETED_EPUB
FOLDER = FOLDER | DELETED_FOLDER

DOCUMENT =  NOTEBOOK | PDF | EPUB
DELETED = (DOCUMENT | FOLDER) << 4
NOT_DELETED = DELETED >> 4
NOTHING = 0
ANYTHING = 0xff


class RemarkableError(Exception):
  pass

class RemarkableDocumentError(RemarkableError):
  pass

class RemarkableSourceError(RemarkableError):
  pass

METADATA = 1
CONTENT = 2
BOTH = 3

# TODO:
# - MoveTo method of index (special case for trash, take care of deleted field)
# - Consider an `update` method for Entry, triggering a save of json files on tablet


class Entry:

  def __init__(self, index, uid, metadata={}, content={}):
    self.index   = index
    self.uid       = uid
    self._metadata  = metadata
    self._content   = content
    self._postInit()

  def _postInit(self):
    pass

  def name(self):
    return self._metadata.get('visibleName')

  def isDeleted(self):
    return self.index.isDeleted(self.uid)

  def updatedOn(self):
    try:
      updated = arrow.get(int(self.lastModified)/1000).humanize()
    except Exception as e:
      updated = self.lastModified or "Unknown"
    return updated

  def cover(self):
    c = self.get('coverPageNumber', -1, CONTENT)
    if c < 0:
      return self.get('lastOpenedPage', 0)
    return c

  def get(self, field, default=None, where=BOTH):
    if field in self._metadata and where & METADATA:
      return self._metadata[field]
    if field in self._content and where & CONTENT:
      return self._content[field]
    return default

  def __getattr__(self, field):
    if field == "fsource" and self.index:
      return self.index.fsource
    if field in self._metadata:
      return self._metadata[field]
    if field in self._content:
      return self._content[field]
    return None
    # raise AttributeError(field)

  # def __setattr__(self, field, val):
  #   print(field,val)
  #   object.__setattr__(self, field, val)

  def __dir__(self):
    return (
      ["name", "updatedOn", "get"]
      + list(self._metadata.keys())
      + list(self._content.keys())
    )



class Folder(Entry):

  def _postInit(self):
    self.files     = []
    self.folders   = []

  def get(self, field, default=None):
    if field == "files":
      yield from self.files
    elif field == "folders":
      yield from self.files
    elif field in self._metadata:
      return self._metadata[field]
    elif field in self._content:
      return self._content[field]
    else:
      return default

  def isRoot(self):
    return False


ROOT_ID = ''
TRASH_ID = 'trash'

class RootFolder(Folder):

  def __init__(self, index, **kw):
    self.index = index
    self.uid = ROOT_ID
    self._metadata  = {
      'visibleName': 'reMarkable',
      'parent': None,
      'deleted': False,
      'type': FOLDER_TYPE
    }
    self._content   = {}
    self._postInit()

  def isRoot(self):
    return True


class TrashBin(Folder):

  def __init__(self, index, **kw):
    self.index = index
    self.uid = TRASH_ID
    self._metadata  = {
      'visibleName': 'Trash',
      'parent': None,
      'deleted': False,
      'type': FOLDER_TYPE
    }
    self._content   = {}
    self._postInit()

  def append(self, entry):
    self.files.append(entry)

  def items(self):
    yield from self.files


class Document(Entry):

  def getPage(self, pageNum):
    pages = self.pages
    try:
      if pages is None:
        pid = str(pageNum)
      else:
        pid = pages[pageNum]
      rmfile = self.fsource.retrieve(self.uid, pid, ext='rm')
      with open(rmfile, 'rb') as f:
        (ver, layers) = readLines(f)
    except:
      ver = 5
      layers = []
    else:
      try:
        mfile = self.fsource.retrieve(self.uid, pid + '-metadata', ext='json')
        with open(mfile, 'r') as f:
          layerNames = json.load(f)
        layerNames = layerNames["layers"]
      except:
        layerNames = [{"name": "Layer %d" % j} for j in range(len(layers))]
      for j in range(len(layers)):
        layers[j] = Layer(layers[j], layerNames[j].get("name"))
    return self._makePage(layers, ver, pageNum)

  def _makePage(self, layers, version, pageNum):
    return Page(layers, version, pageNum, document=self)

  def prefetch(self, progress=None):
    self.fsource.prefetchDocument(self.uid, progress=progress)

  def retrieveBaseDocument(self):
    b = self.baseDocumentName()
    if b:
      return self.fsource.retrieve(b)
    return None

  def baseDocument(self):
    return None

  def baseDocumentName(self):
    return None


Page = namedtuple('Page', ['layers', 'version', 'pageNum', 'document', 'background'],
                                    defaults = [ None,      None,       None ])

Template = namedtuple('Template', ['name', 'retrieve'])

# Here 'background' is either None or a Template object.
# Subclasses of Page may use additional types.
# For annotated pdfs, the underlying PDF page needs to be fetched separately
# and the 'background' field will be None by default.

class Notebook(Document):

  def _postInit(self):
    try:
      pfile = self.fsource.retrieve(self.uid, ext='pagedata')
      with open(pfile) as f:
        self._bg = [t.rstrip('\n') for t in f.readlines()]
    except IOError:
      pass

  def _makePage(self, layers, version, pageNum):
    try:
      t = self._bg[pageNum]
      if t:
        def retrieve(preferVector=False):
          return self.fsource.retrieveTemplate(t)
        template = Template(t, retrieve)
      else:
        template = None
    except:
      template = None
    return Page(layers, version, pageNum, document=self, background=template)


class PDFDoc(Document):

  _pdf = None

  def _makePage(self, layers, version, pageNum):
    return Page(layers, version, pageNum, document=self)

  def markedPages(self):
    for i, p in enumerate(self.pages):
      if self.fsource.exists(self.uid, p, ext='rm'):
        yield i

  def baseDocument(self):
    from popplerqt5 import Poppler
    if self._pdf is None:
      doc = self.retrieveBaseDocument()
      self._pdf = Poppler.Document.load(doc)
      self._pdf.setRenderHint(Poppler.Document.Antialiasing)
      self._pdf.setRenderHint(Poppler.Document.TextAntialiasing)
      try:
        self._pdf.setRenderHint(Poppler.Document.HideAnnotations)
      except Exception:
        pass
    return self._pdf

  def baseDocumentName(self):
    return self.uid + '.pdf'


class EBook(Document):

  def baseDocumentName(self):
    return self.uid + '.epub'


PDF_BASE_METADATA = {
    "deleted": False,
    "metadatamodified": True,
    "modified": True,
    "parent": "",
    "pinned": False,
    "synced": False,
    "type": "DocumentType",
    "version": 0,
}
# "lastModified": "1592831071604",
# "visibleName": ""


PDF_BASE_CONTENT  = {
    "dummyDocument": False,
    "extraMetadata": {},
    "fileType": "pdf",
    "fontName": "",
    "lastOpenedPage": 0,
    "legacyEpub": False,
    "lineHeight": -1,
    "margins": 100,
    "orientation": "portrait",
    "pageCount": 0,
    "textAlignment": "left",
    "textScale": 1,
    "transform": {
      "m11": 1, "m12": 0, "m13": 0,
      "m21": 0, "m22": 1, "m23": 0,
      "m31": 0, "m32": 0, "m33": 1
    }
}





class RemarkableIndex:

  _listeners = {}

  def __init__(self, fsource, progress=(lambda x,tot: None)):
    self.fsource = fsource
    self._uids = list(fsource.listItems())
    index = {ROOT_ID: RootFolder(self)}

    # progress(0, len(self._uids))

    for j, uid in enumerate(self._uids):
      print('%d%%' % (j * 100 // len(self._uids)), end='\r',flush=True)
      progress(j, len(self._uids)*2)
      metadata = self._readJson(uid, ext='metadata')
      content  = self._readJson(uid, ext='content')
      if metadata["type"] == FOLDER_TYPE:
        index[uid] = Folder(self, uid, metadata, content)
      elif metadata["type"] == DOCUMENT_TYPE:
        if content["fileType"] in ["", "notebook"]:
          index[uid] = Notebook(self, uid, metadata, content)
        elif content["fileType"] == "pdf":
          index[uid] = PDFDoc(self, uid, metadata, content)
        elif content["fileType"] == "epub":
          index[uid] = EBook(self, uid, metadata, content)
        else:
          raise RemarkableDocumentError("Unknown file type '{fileType}'".format(content))
      else:
        raise RemarkableDocumentError("Unknown file type '{type}'".format(metadata))
    trash = TrashBin(self)
    for k, prop in index.items():
      progress(len(self._uids)+j, len(self._uids)*2)
      try:
        if prop.deleted or prop.parent == TRASH_ID:
          trash.append(k)
          continue
        parent = prop.parent
        if parent is not None:
          if prop.type == FOLDER_TYPE:
            index[parent].folders.append(k)
          elif prop.type == DOCUMENT_TYPE:
            index[parent].files.append(k)
      except KeyError as e:
        raise RemarkableDocumentError("Could not find field {0} in document {1}".format(e,k))

    self.index = index
    self.trash = trash

  def _readJson(self, *remote, ext=None):
    fname = self.fsource.retrieve(*remote, ext=ext)
    with open(fname) as f:
      return json.load(f)

  NOP = 0 # for acks
  ADD = 1 # adding an item (listener should consider updating parent)
  DEL = 2 # removing item (listener should consider updating parent)
  UPD = 3 # updating metadata of item

  def listen(self, f):
    if not callable(f):
      raise Exception("Listen called on a non-callable argument")
    self._listeners[id(f)] = f
    return id(f)

  def unlisten(self, f):
    return self._listeners.pop(id(f), None) is not None

  def _broadcast(self, success=True, action=NOP, entries=[], **kw):
    for f in self._listeners.values():
      f(success, action, entries, self, kw)



  def isReadOnly(self):
    return self.fsource.isReadOnly()

  def root(self):
    return self.index[ROOT_ID]

  def get(self, uid, exact=True):
    if not exact:
      uid = self.matchId(uid)
    if uid in self.index:
      return self.index[uid]
    else:
      raise RemarkableError("Uid %s not found!" % uid)

  def allUids(self, trashToo=False):
    yield from self._uids
    if trashToo:
      yield from self.trash.items()

  def ancestry(self,uid,exact=True):
    if not exact:
      uid = self.matchId(uid)
    p = []
    while uid:
      if uid in self.index:
        p.append(uid)
        uid = self.index[uid].parent
      else:
        return None
    return reversed(p[1:])

  def pathOf(self,uid, exact=True, delim=None):
    p = map(lambda x: self.index[x].visibleName,
            self.ancestry(uid,exact))
    if delim is None:
      return p
    else:
      return delim.join(p)

  def fullPathOf(self, uid):
    p = self.pathOf(uid, delim='/') + '/' + self.nameOf(uid)
    if not p.startswith('/'):
      p = '/' + p
    return p


  def uidFromPath(self, path, start=None, delim=None):
    p = path
    if delim is not None:
      p = path.rstrip(delim).split(delim)
    if not p:
      return ''
    if start:
      node = self.index[start]
    else:
      node = self.root()
    if p[0] == '':
      node = self.root()
    for name in p[0:-1]:
      if name == '.' or name == '':
        continue
      if name == '..':
        node = self.index[node.parent]
        continue
      newfound = None
      for k in node.folders:
        if self.index[k].visibleName == name:
          newfound = k
          node = self.index[k]
          break
      if not newfound:
        return None
    last = p[-1]
    if last == '.' or last == '':
      return node.uid
    if last == '..':
      return node.parent
    for k in node.folders:
      if self.index[k].visibleName == last:
        return k
    for k in node.files:
      if self.index[k].visibleName == last:
        return k
    return None

  def isOfType(self, uid, mask):
    mask = mask & ANYTHING
    if uid == "":
      return bool(mask & FOLDER) and not (mask & DELETED)
    if uid == TRASH_ID:
      return bool(mask & FOLDER)
    if uid not in self.index:
      return None
    t = 0
    if self.index[uid].type == FOLDER_TYPE:
      t = FOLDER
    elif self.index[uid].fileType in ["", "notebook"]:
      t = NOTEBOOK
    elif self.index[uid].fileType == "pdf":
      t = PDF
    elif self.index[uid].fileType == "epub":
      t = EPUB
    if not self.index[uid].deleted:
      t = t >> 4
    return bool(mask & t)

  def typeOf(self, uid):
    # Usage: bool(index.typeOf(uid) & NOTEBOOK)
    if uid == "" or uid == TRASH_ID:
      return FOLDER
    if uid not in self.index:
      return None
    t = 0
    if self.index[uid].type == FOLDER_TYPE:
      t = FOLDER
    elif self.index[uid].fileType in ["", "notebook"]:
      t = NOTEBOOK
    elif self.index[uid].fileType == "pdf":
      t = PDF
    elif self.index[uid].fileType == "epub":
      t = EPUB
    if not self.index[uid].deleted:
      t = t >> 4
    return t

  def matchId(self, pid, trashToo=False):
    for k in self.index:
      if k.startswith(pid):
        return k
    if trashToo:
      for k in self.trash.items():
        if k.startswith(pid):
          return k
    return None

  def pathOf(self, uid, exact=True, trash_too=False):
    if not exact:
      uid = self.match_id(uid)
    p = []
    while uid:
      if uid in self.index and (trash_too or uid not in self.trash.items()):
          p.append(self.index[uid].visibleName)
          uid = self.index[uid].parent
      else:
        return None
    return reversed(p[1:])

  def findByName(self, name, exact=False):
    if exact:
      for k in self.index:
        if name == self.index[k].visibleName:
          yield k
    else:
      for k in self.index:
        if name in self.index[k].visibleName:
          yield k

  def isFile(self, uid):
    return uid!=ROOT_ID and (uid in self.index and self.index[uid].type == DOCUMENT_TYPE)

  def isFolder(self, uid):
    return uid==ROOT_ID or (uid in self.index and self.index[uid].type == FOLDER_TYPE)

  def updatedOn(self, uid):
    try:
      updated = arrow.get(int(self.lastModifiedOf(uid))/1000).humanize()
    except Exception as e:
      updated = self.lastModifiedOf(uid) or "Unknown"
    return updated

  def nameOf(self, uid):
    return (self.index[uid].visibleName
                if uid in self.index else None)

  def isDeleted(self, uid):
    return uid in self.trash.items()

  def __getattr__(self, field):
    if field.endswith("Of"):
      return (lambda uid:
                self.index[uid].get(field[:-2])
                  if uid in self.index else None)
    else:
      raise AttributeError(field)

  def scanFolders(self, uid=ROOT_ID):
      if isinstance(uid, Entry):
        n = uid
      else:
        n = self.index[uid]
      if isinstance(n, Folder):
        stack = [n]  # stack of folders
        while stack:
          n = stack.pop()
          yield n
          for f in n.folders:
            stack.append(self.index[f])

  def depthFirst(self, uid=ROOT_ID):
      if isinstance(uid, Entry):
        n = uid
      else:
        n = self.index[uid]
      if isinstance(n, Folder):
        stack = [(False, n)]
        while stack:
          visited, node = stack.pop()
          if visited:
            yield n
          else:
            yield from n.files
            for f in n.folders:
              stack.append((False, self.index[f]))
            stack.append((True, n))
      else:
        yield n


  def _newUid(self):
    uid = str(uuid.uuid4())
    while uid in self.index:
      uid = str(uuid.uuid4())
    return uid

  def newPDFDoc(self, pdf, metadata={}, content={}):
    if self.isReadOnly():
      raise RemarkableSourceError("The file source '%s' is read-only" % self.fsource.name)
    uid = self._newUid()
    print(uid)
    meta = PDF_BASE_METADATA.copy()
    meta.setdefault('visibleName', os.path.splitext(os.path.basename(pdf))[0])
    meta.setdefault('lastModified', str(arrow.utcnow().int_timestamp * 1000))
    meta.update(metadata)

    cont = PDF_BASE_CONTENT.copy()
    cont.update(content)

    try:

      self.fsource.upload(pdf, uid + '.pdf')
      self.fsource.store(meta, uid + '.metadata')
      self.fsource.store(cont, uid + '.content')
      self.fsource.store('', uid + '.pagedata')
      self.fsource.makeDir(uid)

      self.index[uid] = d = PDFDoc(self, uid, meta, cont)
      self.index[d.parent].files.append(uid)

      self._broadcast(action=self.ADD, entries=[uid])

      return uid

    except Exception as e:
      print(e)
      self._broadcast(success=False, action=self.ADD, entries=[uid], reason=e)
      # should cleanup if partial upload
      return None
