"""Aggregation, paired comparisons, pre-registered verdict, and the markdown report (v2)."""
import json

PROTOCOL_KEYS = ('min_gain_pp', 'seeds_ge', 'max_cost_ratio')


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def strict(r):
    """Completed on the real end state AND no keep literal was ever violated on the way."""
    return r['judge']['completed'] and not r['keep_violated']


def rate(rs, **flt):
    sel = [r for r in rs if all(r.get(k) == v for k, v in flt.items())]
    return mean(strict(r) for r in sel) if sel else None


def paired(xs, ys):
    tasks = sorted({r['task'] for r in xs})
    seeds = sorted({r['seed'] for r in xs})
    pt = {t: 100 * (rate(xs, task=t) - rate(ys, task=t)) for t in tasks if rate(ys, task=t) is not None}
    ps = {s: 100 * (rate(xs, seed=s) - rate(ys, seed=s)) for s in seeds if rate(ys, seed=s) is not None}
    return {'mean_pp': 100 * (rate(xs) - rate(ys)), 'tasks_pos': sum(v > 0 for v in pt.values()),
            'tasks_neg': sum(v < 0 for v in pt.values()), 'tasks_zero': sum(v == 0 for v in pt.values()),
            'seeds_ge': sum(v >= 0 for v in ps.values()), 'seeds': len(ps), 'per_task_pp': pt, 'per_seed_pp': ps}


def summarize(records, protocol=None, checks=None, learn_costs=None, env=None, sizes=None):
    by = {}
    for r in records:
        by.setdefault(r['condition'], []).append(r)
    s = {'env': env or {}, 'checks': checks or {}, 'learn_cost_s': learn_costs or {}, 'storage': sizes or {},
         'protocol': protocol, 'conditions': {}, 'paired': {}, 'verdict': None}
    for c, rs in sorted(by.items()):
        sc, stops, council = {}, {}, [r['council'] for r in rs if r.get('council')]
        for r in rs:
            for k, v in r['status_counts'].items():
                sc[k] = sc.get(k, 0) + v
            for k, v in r.get('plan_stops', {}).items():
                stops[k] = stops.get(k, 0) + v
        executed = sum(r['actions'] for r in rs)
        s['conditions'][c] = {
            'episodes': len(rs),
            'completion': mean(strict(r) for r in rs),
            'completion_end_state_only': mean(r['judge']['completed'] for r in rs),
            'partial': mean(r['judge']['partial'] for r in rs),
            'keep_violated': sum(r['keep_violated'] for r in rs),
            'actions': mean(r['actions'] for r in rs), 'noops': mean(r['noops'] for r in rs),
            'blocked': sum(r['blocked'] for r in rs), 'abstained': sum(r['abstained'] for r in rs),
            'planner_budget_exceeded': sum(r.get('planner_budget_exceeded', False) for r in rs),
            'budget_exceeded': sum(r['budget_exceeded'] for r in rs), 'env_errors': sum(r['env_errors'] for r in rs),
            'pred_errors': sum(r['pred_errors'] for r in rs), 'pred_total': sum(r['pred_total'] for r in rs),
            'docs_share': (sum(r.get('docs_predictions', 0) for r in rs) / executed) if executed else None,
            'wall_s': mean(r['wall_s'] for r in rs), 'cpu_s': mean(r['cpu_s'] for r in rs),
            'plan_expanded': mean(r['plan_expanded'] for r in rs),
            'plan_predicted': mean(r.get('plan_predicted', 0) for r in rs),
            'peak_mem_mb': max((r.get('peak_mem') or 0 for r in rs), default=0) / 1e6,
            'status_counts': sc, 'plan_stops': stops,
            'by_template': {t: mean(strict(r) for r in rs if r['template'] == t)
                            for t in sorted({r['template'] for r in rs})},
            'council': ({'disagreement': mean(x['disagreements'] / max(1, x['votes']) for x in council),
                         'no_evidence': mean(x.get('no_evidence', 0) / max(1, x['votes']) for x in council)}
                        if council else None),
        }
    for x, y in (('C', 'B'), ('B', 'A'), ('C', 'A'), ('D', 'C')):
        if x in by and y in by:
            s['paired'][f'{x}-{y}'] = paired(by[x], by[y])
    s['verdict'] = verdict(s, protocol)
    return s


def verdict(s, protocol):
    c, ck = s['conditions'], s['checks']
    label = ck.get('label', 'pre-registered')
    if label != 'pre-registered':
        return 'REPLICATION' if str(label).startswith('replication') else 'EXPLORATORY'
    if protocol is None or any(k not in protocol for k in PROTOCOL_KEYS):
        return 'EXPLORATORY'
    invalid = (any(v['env_errors'] for v in c.values()) or ck.get('semantics_ok') is not True
               or ck.get('unreachable', 0) > 0 or ck.get('tests_passed') is not True
               or ('ORACLE' in c and c['ORACLE']['completion'] < 1.0))
    if invalid or 'C-B' not in s['paired']:
        return 'INVALID'
    p = s['paired']['C-B']
    ratio = c['C']['wall_s'] / max(c['B']['wall_s'], 1e-9)
    if (p['mean_pp'] >= protocol['min_gain_pp'] and p['seeds_ge'] >= protocol['seeds_ge']
            and ratio <= protocol['max_cost_ratio']):
        return 'VALID_BOUNDED_GAIN'
    if p['mean_pp'] <= 0:
        return 'VALID_NO_GAIN'
    return 'VALID_INCONCLUSIVE'


def secondary(s, protocol):
    p = s['paired'].get('D-C')
    if p is None or protocol is None or any(k not in protocol for k in PROTOCOL_KEYS):
        return 'n/a'
    if p['mean_pp'] >= protocol['min_gain_pp'] and p['seeds_ge'] >= protocol['seeds_ge']:
        return 'council gain'
    return 'no council gain' if p['mean_pp'] <= 0 else 'council inconclusive'


def report(s):
    c = s['conditions']
    tpls = sorted({t for v in c.values() for t in v['by_template']})
    L = ['# P1 결과 — 동일 경험 시험', '',
         f"판정: **{s['verdict']}**  · 2차(D−C): {secondary(s, s['protocol'])}", '',
         f"protocol: `{json.dumps(s['protocol'], ensure_ascii=False)}`", '',
         f"환경: `{json.dumps(s['env'], ensure_ascii=False)}`", '',
         f"검사: `{json.dumps(s['checks'], ensure_ascii=False)}`", '',
         '## 조건별 (완수 = 평가기 실제 상태 판정 ∧ 도중 keep 위반 없음)', '',
         '| 조건 | 에피소드 | 완수율 | 끝상태만 | 부분충족 | keep위반 | 행동 | no-op | 보류 | 탐색예산초과 | 행동예산초과 | 차단 | 예측오류/예측 | 설명서의존 | wall s | cpu s | 예측/에피소드 | 최대메모리 MB |',
         '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for k, v in c.items():
        ds = '-' if v['docs_share'] is None else f"{v['docs_share']:.2f}"
        L.append(f"| {k} | {v['episodes']} | {v['completion']:.3f} | {v['completion_end_state_only']:.3f} | {v['partial']:.3f} | "
                 f"{v['keep_violated']} | {v['actions']:.2f} | {v['noops']:.2f} | {v['abstained']} | {v['planner_budget_exceeded']} | "
                 f"{v['budget_exceeded']} | {v['blocked']} | {v['pred_errors']}/{v['pred_total']} | {ds} | {v['wall_s']:.3f} | "
                 f"{v['cpu_s']:.3f} | {v['plan_predicted']:.0f} | {v['peak_mem_mb']:.1f} |")
    L += ['', '## 템플릿별 완수율', '', '| 조건 | ' + ' | '.join(tpls) + ' |', '|---|' + '---:|' * len(tpls)]
    for k, v in c.items():
        L.append(f'| {k} | ' + ' | '.join(f"{v['by_template'].get(t, float('nan')):.2f}" for t in tpls) + ' |')
    L += ['', '## Paired 비교 (완수율, 퍼센트포인트)', '',
          '| 비교 | 평균 차이 | 과제 +/0/− | seed ≥0 / 전체 | seed별 |', '|---|---:|---|---|---|']
    for k, p in s['paired'].items():
        L.append(f"| {k} | {p['mean_pp']:+.1f} | {p['tasks_pos']}/{p['tasks_zero']}/{p['tasks_neg']} | "
                 f"{p['seeds_ge']}/{p['seeds']} | {', '.join(f'{sd}:{v:+.0f}' for sd, v in p['per_seed_pp'].items())} |")
    L += ['', '## 예측 근거와 탐색 정지 이유', '']
    for k, v in c.items():
        extra = f"  의결: {json.dumps(v['council'])}" if v.get('council') else ''
        L.append(f"- {k}: status `{json.dumps(v['status_counts'])}`  stops `{json.dumps(v['plan_stops'])}`{extra}")
    L += ['', f"학습 비용(모델 구축 s, seed별): `{json.dumps(s['learn_cost_s'])}`",
          f"저장(journal bytes, seed→조건): `{json.dumps(s['storage'])}`", '',
          '## 주장할 수 없는 것', '',
          '- 위 수치는 생성된 소형 파일 과제에서의 결과다. 자유 언어, UI, 실제 사용자 자료, 자기수정, AGI·의식에 대한 증거가 아니다.',
          '- 같은 학습 상태에서 나온 과제들은 독립 표본이 아니다. seed 5개·과제 20개는 통계적 충분성을 보장하지 않는다.',
          '- ORACLE은 진단 조건이다(planner·과제 타당성). 학습 성과와 비교 대상이 아니다.',
          '- `차단`은 planner가 capability 없는 도구를 계획하지 않으므로 P1에서는 구조적으로 0이다.',
          '- B는 정확 일치 검색이라 탐색 커버리지에 묶인다. C−B에는 "규칙 유도"와 "커버리지 밖 상황의 일반화"가 함께 들어 있다(`설명서의존` 열 참조).', '']
    return '\n'.join(L)
