import json
from copy import deepcopy

import argparse

from collections import namedtuple

import logging
log = logging.getLogger('remy')


def deepupdate(d, u):
  stack = [(d,u)]
  while stack:
    d,u = stack.pop(0)
    for k,v in u.items():
      if not isinstance(v, dict):
        d[k] = v
      else:
        if k not in d:
          d[k] = v
        elif not isinstance(d[k], dict):
          d[k] = v
        else:
          stack.append((d[k], v))
  return d

AppPaths = namedtuple('AppPaths', ['config_dir', 'config', 'known_hosts', 'cache_dir'])
noPaths = AppPaths(None,None,None,None)

class RemyConfigException(Exception):
  pass


OPTIONS_DEFAULTS = {
  "default_source": False,
  "sources": {},
  "log_verbosity": "info",
  "export": {
    "default_dir": "",
    "eraser_mode": "ignore",
    "open_exported": True,
    "include_base_layer": True,
    "orientation": "auto",
    "smoothen": False,
    "simplify": 0,
    "pencil_resolution": 0.4, # Alas QPrinter ignores QBrush's transforms
    "colors": {
      "black": "black",
      "gray": "#bbbbbb",
      "white": "white",
      "highlight": "#55ffeb93"
    }
  },
  "preview": {
    "eraser_mode": "ignore",
    "pencil_resolution": 0.4
  },
  "import": {
    "default_options": {}
  }
}


SOURCE_DEFAULTS = {
  "name": "reMarkable",
  "hidden": False,
  "type": "ssh",
  "host": "10.11.99.1",
  "username": "root",
  "host_key_policy": "ask",
  "timeout": 3,
  "use_banner": False,
  "enable_webui_export": False
}

VERBOSITY = {
  "critical": logging.CRITICAL,
  "error":    logging.ERROR,
  "warning":  logging.WARNING,
  "info":     logging.INFO,
  "debug":    logging.DEBUG,
  "none":     logging.CRITICAL+1
}


class RemyConfig():

  _path = None

  _config = {}
  _source_config = {}
  _original = {}

  _curr_source = None

  # TODO: store AppPaths here, nuke the _default_path _default_cache fields
  #       also handle _path this way
  #       loadFromConfig could be returning desired args to merge, without merging
  #       so that they can be merged after the config file to load has been determined

  def __init__(self, argv=None, paths=noPaths):
    self._paths = paths
    self._config = deepcopy(OPTIONS_DEFAULTS)
    if paths.config and paths.config.is_file():
      self.loadFromConfig(paths.config)
    if argv is not None:
      self.parseArguments(argv)
    # if self._path is not None:
    #   self.loadFromConfig(self._path)
    self.makeConsistent()

  def parseArguments(self, argv):
    # todo: use argparse
    if len(argv) > 1:
      self.selectSource(argv[-1])

  def loadFromConfig(self, path):
    try:
      with open(path) as f:
        self._original = json.load(f)
    except Exception:
      raise RemyConfigException("Could not read configuration from '%s'!" % confpath)
    deepupdate(self._config, self._original)
    self._path = path

  def path(self):
    return self._path

  def selectedSource(self):
    return self._curr_source

  def selectSource(self, source):
    c = self.get("sources")
    if len(c) == 0:
      raise RemyConfigException("No sources specified in configuration.")
    if source not in c:
      raise RemyConfigException("Source '%s' not found in configuration." % source)
    s = c.get(source)
    deepupdate(self._config, s.pop("settings", {}))
    c = deepcopy(SOURCE_DEFAULTS)
    deepupdate(c, s)
    c.setdefault('cache_dir', self._paths.cache_dir)
    c.setdefault('known_hosts', self._paths.known_hosts)
    self._source_config = c
    self._curr_source = source
    self.makeConsistent()

  def get(self, opt, default=None):
    if opt in self._config:
      return self._config[opt]
    if opt in self._source_config:
      return self._source_config[opt]
    if default is None:
      raise RemyConfigException("Option '%s' not found in configuration." % opt)
    return default

  @property
  def export(self):
    return deepcopy(self._config['export'])

  @property
  def import_(self):
    return deepcopy(self._config['import'])

  @property
  def preview(self):
    return deepcopy(self._config['preview'])

  def set(self, opt, v):
    self._config[opt] = v

  def logLevel(self):
    return VERBOSITY.get(self._config['log_verbosity'], logging.INFO)

  def connectionArgs(self, **overrides):
    c = deepcopy(self._source_config)
    c.update(overrides)
    t = c.pop('type')
    return (t, c)

  def makeConsistent(self):
    s = self._source_config
    if s and s.get("use_banner") and s.get("enable_webui_export"):
      s["use_banner"] = False
      log.warning("The `use_banner` setting is incompatible with `enable_webui_export`: the latter is overriding the former.")

  def dump(self, f):
    json.dump(self._config, f, indent=4)

