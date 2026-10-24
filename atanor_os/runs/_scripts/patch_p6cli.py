import pathlib, sys
P = pathlib.Path(sys.argv[1])
p = P / 'atanor_os/eval/p6.py'; s = p.read_text(encoding='utf-8')
if 'def evaluate(' not in s:
    s = s.replace("import copy\nimport hashlib\nimport json\nimport random\n", "import copy\nimport hashlib\nimport json\nimport random\nimport re\n", 1)
    old = "    (out / 'dev_sentences.json').write_text(json.dumps(teacher.DEV_SENTENCES, indent=1), encoding='utf-8')\n"
    assert old in s
    s = s.replace(old, old + "    (out / 'train_sentences.json').write_text(json.dumps(teacher.TRAIN_SENTENCES, indent=1), encoding='utf-8')\n", 1)
    s += (P / 'atanor_os/runs/_scripts/p6_eval_part.py').read_text(encoding='utf-8')
    p.write_text(s, encoding='utf-8')

p = P / 'atanor_os/eval/run.py'; s = p.read_text(encoding='utf-8')
if 'def cmd_p6' not in s:
    old = "def main(argv=None):\n    ap = argparse.ArgumentParser(prog='atanor_os')\n    sub = ap.add_subparsers(dest='cmd', required=True)\n"
    new = '''def cmd_p6(a):
    from . import p6
    if a.cmd == 'p6-train':
        log = p6.train(a.out, n_extra=a.n_extra, reading_epochs=a.reading_epochs)
        print(json.dumps({k: log[k] for k in ('lexicon_epochs', 'teacher_calls', 'web')}, default=str))
    elif a.cmd == 'p6-dev':
        print(json.dumps(p6.dev(a.state, a.out), default=str)[:4000])
    else:
        proto = json.loads(Path(a.protocol).read_text(encoding='utf-8'))
        r = p6.evaluate(a.state, a.sealed, a.commit, a.out, protocol=proto.get('decision_values', {}))
        print(json.dumps({'verdict': r['verdict'], 'summary': r['summary'], 'checks': r['checks']}, default=str))


def main(argv=None):
    ap = argparse.ArgumentParser(prog='atanor_os')
    sub = ap.add_subparsers(dest='cmd', required=True)
    t6 = sub.add_parser('p6-train')
    t6.add_argument('--out', required=True)
    t6.add_argument('--n-extra', type=int, default=60)
    t6.add_argument('--reading-epochs', type=int, default=2)
    d6 = sub.add_parser('p6-dev')
    d6.add_argument('--state', required=True)
    d6.add_argument('--out', required=True)
    e6 = sub.add_parser('p6-eval')
    for k in ('--state', '--sealed', '--commit', '--out', '--protocol'):
        e6.add_argument(k, required=True)
'''
    assert old in s
    s = s.replace(old, new, 1)
    old = "     'compare': cmd_compare, 'supervise': cmd_supervise, 'crash': cmd_crash}[a.cmd](a)"
    assert old in s
    s = s.replace(old, "     'compare': cmd_compare, 'supervise': cmd_supervise, 'crash': cmd_crash, 'p6-train': cmd_p6,\n     'p6-dev': cmd_p6, 'p6-eval': cmd_p6}[a.cmd](a)", 1)
    p.write_text(s, encoding='utf-8')
print('ok')
