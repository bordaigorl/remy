import paramiko
import os
import shutil
import os.path as path
import json
from stat import S_ISREG, S_ISDIR
import subprocess
from shutil import which
from pathlib import PurePosixPath
from threading import RLock

from remy.utils import log



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
    return

  def close(self):
    return

  # def __del__(self):
  #   try:
  #     self.cleanup()
  #     self.close()
  #   except Exception as e:
  #     log.error(e)

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
    self.templatesRoot = None
    if templatesRoot:
      self.templatesRoot = templatesRoot = path.expanduser(templatesRoot)
      self.templates = {}
      with open(path.join(templatesRoot, "templates.json"), 'r', encoding="utf-8") as f:
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
    try:
      return path.join(self.templatesRoot, self._selectTemplate(name, preferVector))
    except Exception:
      log.warning("The template '%s' could not be loaded", name)
      return None

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
    if not ext.startswith('.'): ext = '.' + ext
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

  def __init__(self, ssh, id='', name="SSH", cache_dir=None, username=None, remote_documents=None, remote_templates=None, use_banner=False, connect=True, utils_path='$HOME', persist_cache=True, **kw):
    self.ssh = ssh
    self.name = name
    self.persist_cache = persist_cache

    self.cache_dir = cache_dir = path.join(path.expanduser(cache_dir), id)
    self.local_roots = (
      path.join(cache_dir, 'documents'),
      path.join(cache_dir, 'templates')
    )
    if not persist_cache and path.isdir(cache_dir):
      log.debug("Clearing cache")
      shutil.rmtree(cache_dir, ignore_errors=True)
    self._makeLocalPaths()

    _,out,_ = self.ssh.exec_command("echo $HOME")
    out.channel.recv_exit_status()
    if remote_documents:
      self.remote_roots[0] = remote_documents
    if remote_templates:
      self.remote_roots[1] = remote_templates

    if use_banner:
      self._dirty = True # force restart of xochitl even when stopping failed
      _,out,_ = ssh.exec_command("/bin/systemctl stop xochitl")
      if out.channel.recv_exit_status() == 0:
        _,out,_ = ssh.exec_command(utils_path + "/remarkable-splash '%s'" % use_banner)
        out.channel.recv_exit_status()
      else:
        log.warning("I could not stop xochitl")

    self.sftp = ssh.open_sftp()
    self.scp = self.sftp
    self._lock = RLock()
    # self.scp = SCPClient(ssh.get_transport())

    self.templates = {}

    if connect:
      self.scp.get( self._remote("templates.json", branch=TEMPLDIR)
                    , self._local ("templates.json", branch=TEMPLDIR) )
      with open(self._local("templates.json", branch=TEMPLDIR), 'r', encoding="utf-8") as f:
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
    try:
      p = self.sftp.stat(p)
    except:
      return False
    return S_ISDIR(p.st_mode) != 0

  def _local(self, *paths, branch=DOCSDIR):
    return path.join(self.local_roots[branch], *paths)

  def _remote(self, *paths, branch=DOCSDIR):
    return str(PurePosixPath(self.remote_roots[branch]).joinpath(*paths))

  def isReadOnly(self):
    return False

  def retrieve(self, *filename, ext=None, progress=None, force=False):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    cachep = self._local(*filename)
    with self._lock:
      d = path.dirname(cachep)
      if not path.isdir(d):
        os.makedirs(d)
      remp = self._remote(*filename)
      rstat = self.sftp.stat(remp)
      found = path.isfile(cachep)
      if found:
        lstat = os.stat(cachep)
        force = (force or
          (lstat.st_mtime != rstat.st_mtime) or
          (lstat.st_size != rstat.st_size)
        )
        # not fool-proof but good enough?
        # There is always the option of setting persist_cache: false
        # for the source
      if force or not found:
        self.scp.get(remp, cachep)
        os.utime(cachep, (rstat.st_atime, rstat.st_mtime))
    return cachep

  def retrieveTemplate(self, name, progress=None, force=False, preferVector=False):
    try:
      filename = self._selectTemplate(name, preferVector)
      with self._lock:
        cachep = self._local(filename, branch=TEMPLDIR)
        if force or not path.isfile(cachep):
          remp = self._remote(filename, branch=TEMPLDIR)
          self.scp.get(remp, cachep)
      return cachep
    except Exception:
      log.warning("The template '%s' could not be loaded", name)
      return None

  def prefetchMetadata(self, progress=None, force=False):
    pass
    # for uid in self.listItems():
    #     self.scp.get(self._remote(uid + '.metadata'), self._local())
    #     self.scp.get(self._remote(uid + '.content'), self._local())
    #     if self._isfile(self._remote(uid + '.pagedata')):
    #       self.scp.get(self._remote(uid + '.pagedata'), self._local())

  def prefetchDocument(self, uid, progress=None, force=False):
    with self._lock:
      # self.scp.get(self._remote(uid), self._local(uid), recursive=True)
      if self._isfile(self._remote(uid + '.pdf')):
        self.scp.get(self._remote(uid + '.pdf'), self._local(uid))
      if self._isfile(self._remote(uid + '.epub')):
        self.scp.get(self._remote(uid + '.epub'), self._local(uid))

  def exists(self, *filename, ext=None):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    with self._lock:
      return self._isfile(self._remote(*filename))

  def cleanup(self):
    if not self.persist_cache:
      log.debug("Clearing cache")
      shutil.rmtree(self.cache_dir, ignore_errors=True)
    self.refreshLauncher()

  def refreshLauncher(self, force=False):
    if not self._dirty and not force:
        return
    try:
      for launcher in ['xochitl','tarnish','remux','draft']:
        _,out,_ = self.ssh.exec_command("/bin/systemctl is-enabled " + launcher)
        if out.channel.recv_exit_status() == 0:
          _,out_,_ = self.ssh.exec_command("/bin/systemctl restart " + launcher)
          if out_.channel.recv_exit_status() == 0:
            self._dirty = False
            # No need to check for more than one launcher
            return

    except paramiko.SSHException as e:
      log.warning("Could not restart launcher."
                  "This is most probably due to the tablet going to sleep."
                  "A manual reboot of the tablet is recommended.")
      log.debug("SSH Error: %s", e)

  def listItems(self):
    with self._lock:
      if self._allUids is None:
        self._allUids = []
        for entry in self.sftp.listdir(self._remote()):
          name = path.splitext(entry)
          if name[1] == ".metadata":
            self._allUids.append(name[0])
    return self._allUids

  def listSubItems(self, uid, ext=".rm"):
    folder = self._remote(uid)
    if not ext.startswith('.'): ext = '.' + ext
    try:
      # I don't want to yield while holding a lock
      items = []
      with self._lock:
        for entry in self.sftp.listdir(folder):
          name = path.splitext(entry)
          if name[1] == ext:
            items.append(name[0])
      yield from items
    except Exception as e:
      yield from []

  def upload(self, local, *remote, progress=None, overwrite=False):
    with self._lock:
      if overwrite or not self._isfile(self._remote(*remote)):
        self.sftp.put(local, self._remote(*remote), callback=progress)
        self._dirty = True
        return True
    return False

  def store(self, content, *remote, progress=None, overwrite=False):
    with self._lock:
      if overwrite or not self._isfile(self._remote(*remote)):
        with self.sftp.open(self._remote(*remote), 'w') as f:
          if type(content) is str:
            f.write(content)
          else:
            json.dump(content, f, indent=4)
        self._dirty = True
        return True
    return False

  def remove(self, *remote, progress=None):
    p = self._remote(*remote)
    if self._isfile(p):
      self.sftp.remove(p)
      return True
    return False

  def removeDir(self, *remote, progress=None):
    p = self._remote(*remote)
    with self._lock:
      if self._isdir(p):
        self.sftp.rmdir(p)


  def makeDir(self, *remote):
    try:
      with self._lock:
        self.sftp.mkdir(self._remote(*remote))
      self._dirty = True
      return True
    except:
      return False

  def close(self):
    self.sftp.close()
    self.ssh.close()



class LiveFileSourceRsync(LiveFileSourceSSH):

  RSYNC = [ which("rsync") ]
  _updated = {}

  def __init__(self, ssh, data_dir, name="Rsync",
               username="root", host="10.11.99.1", key=None,
               rsync_path=None, rsync_options=None, remote_documents=None, remote_templates=None,
               use_banner=False, cache_mode="on_demand", known_hosts=None, host_key_policy="ask", **kw):
    LiveFileSourceSSH.__init__(self, ssh, name=name, cache_dir=data_dir,
                               remote_documents=remote_documents, remote_templates=remote_templates,
                               use_banner=use_banner, connect=False)

    log.info("DATA STORED IN:\n\t%s\n\t%s", self.local_roots[0], self.local_roots[1])

    self.host = host
    self.username = username
    self.cache_mode = cache_mode

    if rsync_path:
      self.RSYNC = [ rsync_path ]
    self.RSYNC.append('--info=NAME')

    ssh_config = ['-e', '%s -o batchmode=yes' % which("ssh")]
    if key:
      ssh_config[-1] += ' -i "%s"' % key
    if host_key_policy == "ignore_all":
      ssh_config[-1] += ' -o stricthostkeychecking=no'
    if known_hosts and known_hosts.is_file():
      ssh_config[-1] += ' -o userknownhostsfile="%s"' % known_hosts.resolve()
    self.RSYNC += ssh_config

    if rsync_options:
      if type(rsync_options) == str:
        self.RSYNC.append(rsync_options)
      else:
        self.RSYNC +=rsync_options

    log.debug("RSYNC: %s", self.RSYNC)

    self._bulk_download(
      self._remote(branch=TEMPLDIR),
      self._local (branch=TEMPLDIR),
      excludes=[])

    with open(self._local("templates.json", branch=TEMPLDIR), 'r', encoding="utf-8") as f:
      idx = json.load(f)

    for t in idx["templates"]:
      name = t["filename"] # "name" is just for display, not for lookup!!!
      fname = self._local(t["filename"], branch=TEMPLDIR)
      self.templates[name] = {}
      if path.isfile(fname + '.svg'):
        self.templates[name]['svg'] = t["filename"] + '.svg'
      if path.isfile(fname + '.png'):
        self.templates[name]['png'] = t["filename"] + '.png'

  def _remote_rsync(self, path):
    return "%s@%s:%s" % (self.username, self.host, path)

  def _bulk_download(self, fr, to, excludes=['*'], includes=[], delete=True, progress=None):
    cmd = self.RSYNC + ['-vaz', '--prune-empty-dirs']
    if delete:
      cmd.append('--delete')
    for i in includes:
      cmd.append("--include")
      cmd.append(i)
    for e in excludes:
      cmd.append("--exclude")
      cmd.append(e)
    cmd.append(self._remote_rsync(fr + "/"))
    cmd.append(to)
    if progress:
      with subprocess.Popen(cmd, stdout=subprocess.PIPE) as p:
        for l in p.stdout:
          progress(0,0,"Synching "+l.decode().strip())
        p.wait()
      ret = p.returncode
    else:
      p = subprocess.run(cmd)
      ret = p.returncode
    log.debug("RSYNC returned %s", ret)
    if ret != 0:
      # TODO: would be nicer to capture stderr
      raise Exception("Could not invoke rsync correctly, check your configuration")

  def _file_download(self, fr, to):
    dirname = path.dirname(to)
    if not path.isdir(dirname):
      os.makedirs(dirname)
    return subprocess.run(self.RSYNC + ['-zt', self._remote_rsync(fr), to])

  def retrieve(self, *filename, ext=None, progress=None, force=False):
    if ext:
      filename = filename[:-1] + (filename[-1] + '.' + ext,)
    local = self._local(*filename)
    with self._lock:
      if force or not (path.isfile(local) and local in self._updated):
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
    if self.cache_mode == "full_mirror":
      _excludes = [ ]
      _includes = [ ]
    elif self.cache_mode == "light_mirror":
      _excludes = ['*.thumbnails']
      _includes = [ ]
    else:
      _excludes = [ '*' ]
      _includes = ['*.metadata', '*.content', '*.pagedata']
    self._bulk_download(self._remote(), self._local(),
                        includes=_includes, excludes=_excludes,
                        progress=progress)
    with os.scandir(self._local()) as entries:
      for entry in entries:
        if entry.is_file():
          self._updated[entry.path] = True

  def prefetchDocument(self, uid, progress=None, force=False):
    with self._lock:
      self._bulk_download(self._remote(uid), self._local(uid), excludes=[], progress=progress)
      self._bulk_download(self._remote(uid + '.highlights'), self._local(uid), excludes=[], progress=progress)
      with os.scandir(self._local(uid)) as entries:
        for entry in entries:
          if entry.is_file():
            self._updated[entry.path] = True

  def cleanup(self):
    log.debug("CLEANUP: %s", self._dirty)
    self.refreshLauncher()


