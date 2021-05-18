#!/usr/bin/env python3
import json
from itertools import *
from collections import namedtuple
import arrow
import uuid

from os import stat
from pathlib import Path

from remy.remarkable.lines import *
from remy.remarkable.constants import *

from threading import RLock

import logging
log = logging.getLogger('remy')

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

class RemarkableUidCollision(RemarkableError):
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

  def isFolder(self):
    return self.index.isFolder(self.uid)

  def isTrash(self):
    return self.index.isTrash(self.uid)

  def parentEntry(self):
    return self.index.get(self.parent)

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
      ["name", "updatedOn", "isDeleted", "get", "fsource"]
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
      except Exception:
        layerNames = [{"name": "Layer %d" % j} for j in range(len(layers))]

      highlights = {}
      try:
        if self.fsource.exists(self.uid + '.highlights', pid, ext='json'):
          hfile = self.fsource.retrieve(self.uid + '.highlights', pid, ext='json')
          with open(hfile, 'r') as f:
            h = json.load(f).get('highlights', [])
          for i in range(len(h)):
            highlights[i] = h[i]
      except Exception:
        pass # empty highlights are ok

      for j in range(len(layers)):
        layers[j] = Layer(layers[j], layerNames[j].get("name"), highlights.get(j, []))

    return self._makePage(layers, ver, pageNum)

  def _makePage(self, layers, version, pageNum):
    return Page(layers, version, pageNum, document=self)

  def prefetch(self, progress=None):
    self.fsource.prefetchDocument(self.uid, progress=progress)

  def retrieveBaseDocument(self):
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


class PDFBasedDoc(Document):

  _pdf = None
  _pdf_lock = RLock()

  def _makePage(self, layers, version, pageNum):
    return Page(layers, version, pageNum, document=self)

  def markedPages(self):
    for i, p in enumerate(self.pages):
      if self.fsource.exists(self.uid, p, ext='rm'):
        yield i

  def retrieveBaseDocument(self):
    b = self.baseDocumentName()
    if b and self.fsource.exists(b):
      return self.fsource.retrieve(b)
    return None

  def baseDocument(self):
    from popplerqt5 import Poppler
    with self._pdf_lock:
      if self._pdf is None:
        doc = self.retrieveBaseDocument()
        if doc is None:
          log.warning("Base document for %s could not be found", self.uid)
          return None
        self._pdf = Poppler.Document.load(doc)
        self._pdf.lock = RLock()
        self._pdf.setRenderHint(Poppler.Document.Antialiasing)
        self._pdf.setRenderHint(Poppler.Document.TextAntialiasing)
        try:
          self._pdf.setRenderHint(Poppler.Document.HideAnnotations)
        except Exception:
          pass
    return self._pdf

  def baseDocumentName(self):
    return self.uid + '.pdf'

  def originalName(self):
    return self.uid + '.pdf'


class PDFDoc(PDFBasedDoc):
  pass


class EBook(PDFBasedDoc):

  def originalName(self):
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


FOLDER_METADATA = {
    "deleted": False,
    "metadatamodified": True,
    "modified": True,
    "parent": "",
    "pinned": False,
    "synced": False,
    "type": "CollectionType",
    "version": 0,
    # "lastModified": "timestamp",
    # "visibleName": "..."
}


class RemarkableIndex:

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

  def _new_entry_prepare(self, uid, etype, meta, path=None):
    pass # for subclasses to specialise

  def _new_entry_progress(self, uid, done, tot):
    pass # for subclasses to specialise

  def _new_entry_error(self, exception, uid, etype, meta, path=None):
    pass # for subclasses to specialise

  def _new_entry_complete(self, uid, etype, meta, path=None):
    pass # for subclasses to specialise

  def _update_entry_prepare(self, uid, etype, new_meta):
    pass # for subclasses to specialise

  def _update_entry_complete(self, uid, etype, new_meta):
    pass # for subclasses to specialise

  def _update_entry_error(self, exception, uid, etype, new_meta):
    pass # for subclasses to specialise


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


  def uidFromPath(self, path, start=ROOT_ID, delim=None):
    p = path
    if delim is not None:
      p = path.rstrip(delim).split(delim)
    if not p:
      return ROOT_ID
    node = self.index[start]
    if p[0] == '' or p[0] == '/':
      node = self.root()
    for name in p[0:-1]:
      if name == '.' or name == '' or name == '/':
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
    if last == '.' or last == '' or last == '/':
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

  def isTrash(self, uid):
    return uid==TRASH_ID

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

  ### Concurrency assumption:
  ### a client of RemarkableIndex has to ensure that there are
  ### max 1 writer (readers are unlimited)

  _reservedUids = set()

  def reserveUid(self):
    # collisions are highly unlikely, but good to check
    uid = str(uuid.uuid4())
    while uid in self.index or uid in self._reservedUids:
      uid = str(uuid.uuid4())
    self._reservedUids.add(uid)
    return uid

  def newFolder(self, uid=None, metadata={}, progress=None):
    try:
      if self.isReadOnly():
        raise RemarkableSourceError("The file source '%s' is read-only" % self.fsource.name)

      if not uid:
        uid = self.reserveUid()

      log.info("Preparing creation of %s", uid)
      self._new_entry_prepare(uid, FOLDER, metadata)

      def p(x):
        if callable(progress):
          progress(x, 2)
        self._new_entry_progress(uid, x, 2)

      if self.fsource.exists(uid, ext="metadata"):
        raise RemarkableUidCollision("Attempting to create new document but chosen uuid is in use")

      p(0)

      meta = FOLDER_METADATA.copy()
      meta.setdefault('visibleName', 'New Folder')
      meta.setdefault('lastModified', str(arrow.utcnow().int_timestamp * 1000))
      meta.update(metadata)
      if not self.isFolder(meta["parent"]):
        raise RemarkableError("Cannot find parent %s" % meta["parent"])

      self.fsource.store(meta, uid + '.metadata')
      p(1)
      self.fsource.store({}, uid + '.content')
      p(2)

      self.index[uid] = d = Folder(self, uid, meta, {})
      self.index[d.parent].files.append(uid)
      self._reservedUids.pop(uid, None)

      self._new_entry_complete(uid, FOLDER, metadata)
      return uid
    except Exception as e:
      # cleanup if partial upload
      self.fsource.remove(uid + '.metadata')
      self.fsource.remove(uid + '.content')
      self._new_entry_error(e, uid, FOLDER, metadata)
      raise e


  def newPDFDoc(self, pdf=None, uid=None, metadata={}, content={}, progress=None):
    try:

      if self.isReadOnly():
        raise RemarkableSourceError("The file source '%s' is read-only" % self.fsource.name)

      if not uid:
        uid = self.reserveUid()
      pdf = Path(pdf)

      log.info("Preparing creation of %s", uid)
      self._new_entry_prepare(uid, PDF, metadata, pdf)

      totBytes = 0
      if callable(progress):
        def p(x):
          progress(x, totBytes)
          self._new_entry_progress(uid, x, totBytes)
        def up(x, t):
          p(400+x)
      else:
        def p(x,t=0): pass
        up = None

      if self.fsource.exists(uid, ext="metadata"):
        raise RemarkableUidCollision("Attempting to create new document but chosen uuid is in use")

      meta = PDF_BASE_METADATA.copy()
      meta.setdefault('visibleName', pdf.stem)
      meta.setdefault('lastModified', str(arrow.utcnow().int_timestamp * 1000))
      meta.update(metadata)
      if not self.isFolder(meta["parent"]):
        raise RemarkableError("Cannot find parent %s" % meta["parent"])

      cont = PDF_BASE_CONTENT.copy()
      cont.update(content)

      # imaginary 100bytes per json file
      totBytes = 400 + stat(pdf).st_size

      p(0)
      self.fsource.store(meta, uid + '.metadata')
      p(200)
      self.fsource.store(cont, uid + '.content')
      p(300)
      self.fsource.store('', uid + '.pagedata')
      p(400)
      self.fsource.upload(pdf, uid + '.pdf', progress=up)
      self.fsource.makeDir(uid)

      self.index[uid] = d = PDFDoc(self, uid, meta, cont)
      self.index[d.parent].files.append(uid)
      self._reservedUids.discard(uid)

      p(totBytes)
      self._new_entry_complete(uid, PDF, metadata, pdf)

      return uid

    except Exception as e:
      # cleanup if partial upload
      self.fsource.remove(uid + '.pdf')
      self.fsource.remove(uid + '.metadata')
      self.fsource.remove(uid + '.content')
      self.fsource.remove(uid + '.pagedata')
      self.fsource.removeDir(uid)
      self._new_entry_error(e, uid, PDF, metadata, pdf)
      raise e
