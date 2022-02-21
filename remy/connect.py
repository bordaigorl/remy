# from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


import paramiko
import struct
import time
from binascii import hexlify

import sys
import os

from remy.utils import log

import socket

BadHostKeyException = paramiko.BadHostKeyException

class TimeoutException(Exception):
  pass

class UnknownHostKeyException(paramiko.SSHException):

  def __init__(self, hostname, key):
    paramiko.SSHException.__init__(self, hostname, key)
    self.hostname = hostname
    self.key = key

  def __str__(self):
    msg = "Unknown host key for server '{}': got '{}'"
    return msg.format(
        self.hostname,
        self.key.get_base64(),
    )

AddNewHostKey = paramiko.AutoAddPolicy


class RejectNewHostKey(paramiko.MissingHostKeyPolicy):

  def missing_host_key(self, client, hostname, key):
    raise UnknownHostKeyException(hostname, key)


class IgnoreNewHostKey(paramiko.MissingHostKeyPolicy):

  def missing_host_key(self, client, hostname, key):
    log.warning("Unknown %s host key for %s: %s", key.get_name(), hostname, hexlify(key.get_fingerprint()))


HOST_KEY_POLICY = {
  "ask": RejectNewHostKey,
  "ignore_new": IgnoreNewHostKey,
  "ignore_all": IgnoreNewHostKey,
  "auto_add": AddNewHostKey
}

def connect(address='10.11.99.1', username='root', password=None, key=None, timeout=3,
            host_key_policy=None, known_hosts=None, **kwargs):

  if key is not None:
    key = os.path.expanduser(key)

    if password:
      # password protected key file, password provided in the config
      pkey = paramiko.RSAKey.from_private_key_file(key, password=password)
    else:
      try:
        pkey = paramiko.RSAKey.from_private_key_file(key)
      except paramiko.ssh_exception.PasswordRequiredException:
        passphrase, ok = QInputDialog.getText(None, "Configuration","SSH key passphrase:",
                                              QLineEdit.Password)
        if ok:
          pkey = paramiko.RSAKey.from_private_key_file(key, password=passphrase)
        else:
          raise Exception("A passphrase for SSH key is required")
  else:
    pkey = None
    if password is None:
      log.warning("No key nor password given. System-wide SSH connection parameters are going to be used.")

  client = paramiko.SSHClient()

  if host_key_policy != "ignore_all":
    if known_hosts and known_hosts.is_file():
      log.info("Using known hosts file: %s" % (known_hosts))
      client.load_host_keys(known_hosts)
      log.info("Loaded known hosts from %s", known_hosts)
    else:
      log.info("Using system default known hosts file")
      log.info("Loading system default known hosts file, this may take a while...")
      # ideally we would want to always load the system ones
      # and have the local keys have precedence, but paramiko gives
      # always precedence to system keys
      # There is extremly slow in system with many known host entries... :/
      # See https://github.com/paramiko/paramiko/issues/191
      client.load_system_host_keys()
      log.info("System default known host file loaded")

  policy = HOST_KEY_POLICY.get(host_key_policy, RejectNewHostKey)
  client.set_missing_host_key_policy(policy())

  options = {
    'username': username,
    'password': password,
    'pkey':     pkey,
    'timeout':  timeout,
    'disabled_algorithms': dict(pubkeys=["rsa-sha2-512", "rsa-sha2-256"]),
  }

  try:
    log.info('Connecting...') # pkey=key,
    client.connect(address, **options)
    log.info("Connected to %s", address)
    client.hostname = address
  except socket.timeout as e:
    log.error("Could not connect to %s: %s", address, e)
    raise TimeoutException("Timeout reached, please check your remarkable is connected and retry.")
  except Exception as e:
    log.error("Could not connect to %s: %s", address, e)
    raise e
  try:
    if known_hosts and known_hosts.is_file():
      client.save_host_keys(known_hosts)
  except Exception as e:
    log.warning("Could not save known keys at '%s'" % known_hosts)

  return client
