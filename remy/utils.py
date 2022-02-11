
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

