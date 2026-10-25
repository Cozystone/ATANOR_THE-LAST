import pathlib, sys
p = pathlib.Path(sys.argv[1]); s = p.read_text(encoding='utf-8')
old = "            surprise = (predicted is None) == ok or (ok and any(predicted[a].get(k) not in ('unknown', post[a].get(k)) for a in args for k in ('kind', 'hash')))"
new = "            surprise = (predicted is None) == ok or (ok and any(predicted[a].get(k) not in ('unknown', post[a].get(k)) for a in args for k in predicted[a]))"
assert old in s, 'surprise anchor'; p.write_bytes(s.replace(old, new, 1).encode('utf-8')); print('surprise generalized')
