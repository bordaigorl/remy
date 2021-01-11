import paramiko
import os
import shutil
import os.path as path
import json
from stat import S_ISREG, S_ISDIR
import subprocess

import logging
log = logging.getLogger('remy')


class Progress():

  def started(self, total):
    pass

  def aborted(self, reason):
    pass

  def progress(self, step, total):
    pass

  def finished(self):
    pass



class FileSource():
  """
  An abstraction over reMarkable's data folder.
  Should guarantee thread safety if used on disjoint paths.
  """

  def isReadOnly(self):
    """Don't try uploading if it is readOnly!"""
    return True

  def needsRestart(self):
    return False

  def retrieve(self, *remote, progress=None, force=False):
    """
    Given a path `filename` relative to the documents root
    return a local path with the data in it.
    """
    raise NotImplementedError

  def retrieveTemplate(self, name, progress=None, force=False, preferVector=False):
    """
    Given a path `filename` relative to the documents root
    return a local path with the data in it.
    """
    raise NotImplementedError

  def upload(self, local, *remote, progress=None, overwrite=False):
    raise NotImplementedError

  def store(self, content, *remote, progress=None, overwrite=False):
    """
    If `content` is not a string, it gets converted to json
    """
    raise NotImplementedError

  def makeDir(self, *remote):
    raise NotImplementedError

  def prefetchMetadata(self, progress=None, force=False):
    raise NotImplementedError

  def prefetchDocument(self, uid, progress=None, force=False):
    raise NotImplementedError

  def exists(self, *filename, ext=None):
    raise NotImplementedError

  def cleanup(self):
    raise NotImplementedError

  def listItems(self):
    raise NotImplementedError

  def listSubItems(self, uid, ext="rm"):
    raise NotImplementedError

  def _selectTemplate(self, name, preferVector=False):
    # try:
      if 'png' in self.templates[name]:
        if 'svg' in self.templates[name]:
          if preferVector:
            return self.templates[name]['svg']
        return self.templates[name]['png']
      else:
        return self.templates[name]['svg']
    # except:
      # return None



class LocalFileSource(FileSource):
  """An abstraction over a local backup folder"""
  def __init__(self, name, root, templatesRoot=None):
    self.name = name
    self.root = root = path.expanduser(root)
    self.templatesRoot = templatesRoot = path.expanduser(templatesRoot)
    if templatesRoot:
      self.templates = {}
      with open(path.join(templatesRoot, "templates.json"), 'r') as f:
        idx = json.load(f)
      for t in idx["templates"]:
        name = t["filename"] # "name" is just for display, not for lookup!!!
        fname = path.join(templatesRoot, t["filename"])
        self.templates[name] = {}
        if path.isfile(fname + '.svg'):
          self.templates[name]['svg'] = t["filename"] + '.svg'
        if path.isfile(fname + '.png'):
          self.templates[name]['png'] = t["filename"] + '.png'

  def isReadOnly(self):
    return True

  def retrieve(self, *filename, ext=None, progress=None, force=False):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    return path.join(self.root, *filename)

  def retrieveTemplate(self, name, progress=None, force=False, preferVector=False):
    return path.join(self.templatesRoot, self._selectTemplate(name, preferVector))

  def prefetchMetadata(self, progress=None, force=False):
    pass

  def prefetchDocument(self, uid, progress=None, force=False):
    pass

  def exists(self, *filename, ext=None):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    return path.isfile(path.join(self.root, *filename))

  def cleanup(self):
    pass

  def listItems(self):
    with os.scandir(self.root) as entries:
      for entry in entries:
        if entry.is_file():
          name = path.splitext(entry.name)
          if name[1] == ".metadata":
            yield name[0]

  def listSubItems(self, uid, ext=".rm"):
    folder = path.join(self.root, uid)
    if path.isdir(folder):
      with os.scandir(folder) as entries:
        for entry in entries:
          if entry.is_file():
            name = path.splitext(entry.name)
            if name[1] == ext:
              yield name[0]



DOCSDIR = 0
TEMPLDIR = 1


class LiveFileSourceSSH(FileSource):

  remote_roots = (
    '/home/root/.local/share/remarkable/xochitl',
    '/usr/share/remarkable/templates'
  )

  _allUids = None

  _dirty = False

  def __init__(self, name, ssh, cache_dir=None, use_banner=False, **kw):
    self.ssh = ssh
    self.name = name
    self.cache_dir = cache_dir = path.expanduser(cache_dir)
    self.local_roots = (
      path.join(cache_dir, 'documents'),
      path.join(cache_dir, 'templates')
    )
    self._makeLocalPaths()

    if use_banner:
      _,out,_ = ssh.exec_command("/bin/systemctl stop xochitl")
      if out.channel.recv_exit_status() == 0:
        self._dirty = True
        _,out,_ = ssh.exec_command("remarkable-splash '%s'" % use_banner)
        out.channel.recv_exit_status()
      else:
        log.warning("I could not stop xochitl")

    self.sftp = ssh.open_sftp()
    self.scp = self.sftp
    # self.scp = SCPClient(ssh.get_transport())

    self.templates = {}
    self.scp.get( self._remote("templates.json", branch=TEMPLDIR)
                , self._local ("templates.json", branch=TEMPLDIR) )
    with open(self._local("templates.json", branch=TEMPLDIR), 'r') as f:
      idx = json.load(f)

    for t in idx["templates"]:
      name = t["filename"] # "name" is just for display, not for lookup!!!
      fname = self._remote(t["filename"], branch=TEMPLDIR)
      self.templates[name] = {}
      if self._isfile(fname + '.svg'):
        self.templates[name]['svg'] = t["filename"] + '.svg'
      if self._isfile(fname + '.png'):
        self.templates[name]['png'] = t["filename"] + '.png'


  def _makeLocalPaths(self):
    for dirname in self.local_roots:
      if not path.isdir(dirname):
        os.makedirs(dirname)

  def _isfile(self, p):
    try:
      p = self.sftp.stat(p)
    except:
      return False
    return S_ISREG(p.st_mode) != 0

  def _isdir(self, p):
    p = self.sftp.stat(p)
    return S_ISDIR(p.st_mode) != 0

  def _local(self, *paths, branch=DOCSDIR):
    return path.join(self.local_roots[branch], *paths)

  def _remote(self, *paths, branch=DOCSDIR):
    return path.join(self.remote_roots[branch], *paths)

  def isReadOnly(self):
    return False

  def retrieve(self, *filename, ext=None, progress=None, force=False):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    cachep = self._local(*filename)
    d = path.dirname(cachep)
    if not path.isdir(d):
      os.makedirs(d)
    if force or not path.isfile(cachep):
      remp = self._remote(*filename)
      self.scp.get(remp, cachep)
    return cachep

  def retrieveTemplate(self, name, progress=None, force=False, preferVector=False):
    filename = self._selectTemplate(name, preferVector)
    cachep = self._local(filename, branch=TEMPLDIR)
    if force or not path.isfile(cachep):
      remp = self._remote(filename, branch=TEMPLDIR)
      self.scp.get(remp, cachep)
    return cachep

  def prefetchMetadata(self, progress=None, force=False):
    pass
    # for uid in self.listItems():
    #     self.scp.get(self._remote(uid + '.metadata'), self._local())
    #     self.scp.get(self._remote(uid + '.content'), self._local())
    #     if self._isfile(self._remote(uid + '.pagedata')):
    #       self.scp.get(self._remote(uid + '.pagedata'), self._local())

  def prefetchDocument(self, uid, progress=None, force=False):
    # self.scp.get(self._remote(uid), self._local(uid), recursive=True)
    if self._isfile(self._remote(uid + '.pdf')):
      self.scp.get(self._remote(uid + '.pdf'), self._local(uid))
    if self._isfile(self._remote(uid + '.epub')):
      self.scp.get(self._remote(uid + '.epub'), self._local(uid))

  def exists(self, *filename, ext=None):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    return self._isfile(self._remote(*filename))

  def cleanup(self):
    shutil.rmtree(self.cache_dir, ignore_errors=True)
    if self._dirty:
      _,out,_ = self.ssh.exec_command("/bin/systemctl restart xochitl")
      out.channel.recv_exit_status()

  def listItems(self):
    if self._allUids is None:
      self._allUids = []
      for entry in self.sftp.listdir(self._remote()):
        name = path.splitext(entry)
        if name[1] == ".metadata":
          self._allUids.append(name[0])
    return self._allUids

  def listSubItems(self, uid, ext="rm"):
    folder = self._remote(uid)
    ext = '.' + ext
    try:
      for entry in self.sftp.listdir(folder):
        name = path.splitext(entry)
        if name[1] == ext:
          yield name[0]
    except Exception as e:
      return

  def upload(self, local, *remote, progress=None, overwrite=False):
    if overwrite or not self._isfile(self._remote(*remote)):
      self.sftp.put(local, self._remote(*remote))
      self._dirty = True
      return True
    return False

  def store(self, content, *remote, progress=None, overwrite=False):
    if overwrite or not self._isfile(self._remote(*remote)):
      with self.sftp.open(self._remote(*remote), 'w') as f:
        if type(content) is str:
          f.write(content)
        else:
          json.dump(content, f, indent=4)
      self._dirty = True
      return True
    return False

  def makeDir(self, *remote):
    try:
      self.sftp.mkdir(self._remote(*remote))
      self._dirty = True
      return True
    except:
      return False



class LiveFileSourceRsync(LiveFileSourceSSH):

  RSYNC = [ "rsync" ]
  _updated = {}

  def __init__(self, name, ssh, data_dir, host=None, rsync_path=None, rsync_options=None, use_banner=False, **kw):
    self.ssh = ssh
    self.name = name
    self.cache_dir = path.expanduser(data_dir)
    self.local_roots = (
      path.join(self.cache_dir, 'documents'),
      path.join(self.cache_dir, 'templates')
    )
    self._makeLocalPaths()
    log.info("DATA STORED IN:\n\t%s\n\t%s", self.local_roots[0], self.local_roots[1])

    if use_banner:
      _,out,_ = ssh.exec_command("/bin/systemctl stop xochitl")
      if out.channel.recv_exit_status() == 0:
        self._dirty = True
        _,out,_ = ssh.exec_command("$HOME/remarkable-splash '%s'" % use_banner)
        out.channel.recv_exit_status()
      else:
        log.warning("I could not stop xochitl")

    self.host = host or ssh.address
    self.sftp = self.scp = ssh.open_sftp()  # for listing
    if rsync_path:
      self.RSYNC = [ rsync_path ]
    if rsync_options:
      if type(rsync_options) == str:
        self.RSYNC.append(rsync_options)
      else:
        self.RSYNC +=rsync_options

    self._bulk_download(
      self._remote(branch=TEMPLDIR),
      self._local (branch=TEMPLDIR),
      excludes=[])

    self.templates = {}
    with open(self._local("templates.json", branch=TEMPLDIR), 'r') as f:
      idx = json.load(f)

    for t in idx["templates"]:
      name = t["filename"] # "name" is just for display, not for lookup!!!
      fname = self._local(t["filename"], branch=TEMPLDIR)
      self.templates[name] = {}
      if path.isfile(fname + '.svg'):
        self.templates[name]['svg'] = t["filename"] + '.svg'
      if path.isfile(fname + '.png'):
        self.templates[name]['png'] = t["filename"] + '.png'

  def _bulk_download(self, fr, to, excludes=['*'], includes=[], delete=True):
    cmd = self.RSYNC + ['-vaz', '--prune-empty-dirs']
    if delete:
      cmd.append('--delete')
    for i in includes:
      cmd.append("--include")
      cmd.append(i)
    for e in excludes:
      cmd.append("--exclude")
      cmd.append(e)
    cmd.append("%s:'%s/'" % (self.host, fr))
    cmd.append(to)
    return subprocess.run(cmd)

  def _file_download(self, fr, to):
    dirname = path.dirname(to)
    if not path.isdir(dirname):
      os.makedirs(dirname)
    return subprocess.run(self.RSYNC + ['-zt', self.host + ':' + fr, to])

  def retrieve(self, *filename, ext=None, progress=None, force=False):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    local = self._local(*filename)
    if not (path.isfile(local) and local in self._updated):
      if not self._isfile(self._remote(*filename)):
        return None
      self._file_download(self._remote(*filename), local)
      self._updated[local] = True
    return local

  def retrieveTemplate(self, name, progress=None, force=False, preferVector=False):
    try:
      t = self._selectTemplate(name, preferVector)
      return self._local(t, branch=TEMPLDIR)
    except Exception:
      log.warning("The template '%s' could not be loaded", name)
      return None

  def prefetchMetadata(self, progress=None, force=False):
    self._bulk_download(self._remote(), self._local(), includes=['*.metadata', '*.content', '*.pagedata'])
    with os.scandir(self._local()) as entries:
      for entry in entries:
        if entry.is_file():
          self._updated[entry.path] = True

  def prefetchDocument(self, uid, progress=None, force=False):
    self._bulk_download(self._remote(uid), self._local(uid), excludes=[])
    with os.scandir(self._local(uid)) as entries:
      for entry in entries:
        if entry.is_file():
          self._updated[entry.path] = True

  def cleanup(self):
    if self._dirty:
      _,out,_ = self.ssh.exec_command("/bin/systemctl restart xochitl")
      out.channel.recv_exit_status()





# Factory

def fileSourceFromSSH(cls, name="SSH", address='10.11.99.1', username='root', password=None, key=None, timeout=1, **kw):
  # try:
    client = paramiko.SSHClient()
    client.load_system_host_keys()

    if key is not None:
      key = os.path.expanduser(key)
      try:
        pkey = paramiko.RSAKey.from_private_key_file(key)
      except paramiko.ssh_exception.PasswordRequiredException:
        passphrase, ok = QInputDialog.getText(None, "Configuration","SSH key passphrase:", QLineEdit.Password)
        if ok:
          pkey = paramiko.RSAKey.from_private_key_file(key, password=passphrase)
        else:
          raise Exception("A passphrase for SSH key is required")
    else:
      pkey = None
      if password is None:
        raise Exception("Must provide either password or SSH key")

    options = {
      'username': username,
      'password': password,
      'pkey': pkey,
      'timeout': timeout,
      'look_for_keys': False
    }
    log.info('Connecting...') # pkey=key,
    client.connect(address, **options)
    log.info("Connected to %s", address)
    client.address = address
    return cls(name, client, **kw)
  # except Exception as e:
  #   log.error("Could not connect to %s: %s", address, e)
  #   log.error("Please check your remarkable is connected and retry.")
  #   return None


