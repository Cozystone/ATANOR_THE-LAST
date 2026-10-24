import json, hashlib, pathlib
A = pathlib.Path('atanor_os')
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
rows = [json.loads(l) for l in open(A / 'results/p7-dev/model_calls_on.jsonl', encoding='utf-8')]
summ = {'model': rows[0]['model'], 'digest': rows[0]['digest'], 'prompt_version': rows[0]['prompt_version'], 'calls': len(rows),
        'prompt_tokens': sum((r.get('usage') or {}).get('prompt_tokens') or 0 for r in rows), 'output_tokens': sum((r.get('usage') or {}).get('output_tokens') or 0 for r in rows),
        'seconds': round(sum(r['seconds'] for r in rows), 1), 'accepted': sum(len(r['accepted']) for r in rows), 'rejected_by_verification': sum(len(r['rejected']) for r in rows),
        'per_call': [{'ext': r['ext'], 'excerpt_sha256': r['excerpt_sha256'], 'excerpt_chars': r['excerpt_chars'], 'accepted_values': [c['value'] for c in r['accepted']],
                      'n_rejected': len(r['rejected']), 'seconds': r['seconds']} for r in rows]}
(A / 'results/p7-dev/model_calls_summary.json').write_text(json.dumps(summ, indent=1, ensure_ascii=False), encoding='utf-8')
proto = {
 "version": 1, "name": "P7 - ATANOR decision layer with a language model as reading tool", "frozen_at": "2026-10-24T20:10:00", "design": "P7_DESIGN.md",
 "user_decisions": "direction (b); the model only extracts quote-backed fact candidates from excerpts ATANOR chose; goal interpretation, next search/visit, source trust, adopt/hold and actions are ATANOR decisions; model-on and model-off evaluated together; model-read results are not counted as ATANOR learning language; report model version/digest, calls and cost; if results are low, do not widen the model role - report the failure point",
 "model": {"name": "qwen2.5:7b-instruct", "digest": "845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e", "params": "7.6B", "quantization": "Q4_K_M", "license": "Apache-2.0",
           "runtime": "Ollama 0.40.3, separate server on 127.0.0.1:11435 with its own model folder (the existing user Ollama store reports every manifest as unreadable; left untouched)",
           "options": {"temperature": 0, "seed": 7, "num_predict": 300}, "prompt_version": "p7-extract-v1",
           "interface": "agent/perception.py extract(excerpt, ext) -> quote-verified candidates"},
 "atanor_state": {"file": "results/h6-train/state.json", "sha256": sha(A / 'results/h6-train/state.json'), "note": "H6-1 trained state; no new training in P7; teacher off"},
 "pool": {"file": "results/p7-truth/pool.json", "sha256": sha(A / 'results/p7-truth/pool.json'), "n": 267,
          "rule": "Wikidata file formats with one English label, unused in P6 training/dev, H6 transfer and P6 pools"},
 "draw": "32 evaluation formats = random.Random(int(sha256(public freeze commit hash)) mod 2^31).sample(sorted(pool), 32)",
 "sealed_sentences": {"location": "outside the repository: D:/ATANOR-experiments/2026-09-19/sealed/p7_eval_sentences.json",
                      "sha256": "4c7b67bb96473e06d48aa71a6ee253960cd9009ce970942589dc1211af95b076",
                      "written_by": "agent without the teacher context; original published after the run"},
 "tasks": {"possible": 30, "impossible": 6, "files_per_task": 3, "forms": ["folder", "rename", "copy"]},
 "conditions": {"F_LM": "ATANOR + model (two agreeing pages)", "S_LM": "ATANOR + model, first trusted page (no agreement)", "F": "ATANOR, model off",
                "N": "no web", "ORACLE": "truth names + given form"},
 "primary": "strict completion on possible tasks; F_LM vs N (with tool) and F vs N (model off), paired by task",
 "decision_values": {"min_gain_pp": 30, "min_completion": 0.5, "min_correct_stops_frac": 0.6667, "max_wrong_per_task": 0.5, "no_gain_completion": 0.2},
 "verdicts": {"verdict_with_tool": "computed for F_LM; credited to ATANOR + reading tool, NOT to ATANOR language",
              "verdict_model_off": "computed for F; the only one that can support a claim that ATANOR learned something"},
 "invalid_if": ["teacher import attempted", "any model call in a model-off condition", "LLM/localhost host requested through the web body",
                "sentence overlap with training/dev material", "ORACLE completion < 1.0", "sealed file inside the repository"],
 "secondary": ["per-file success rate", "adoption precision/recall per condition", "stop reasons (no evidence / single source / contradiction)",
               "F_LM vs S_LM (value of the agreement rule)", "trigger validity", "rehearsal (sandbox) outcomes vs real outcomes",
               "model calls, tokens, GPU seconds, verification rejections", "goal interpretation accuracy (model-free)"],
 "expectation_before_run": "From the model-on dev check (44 never-taught formats): adoption recall 0.20 at precision 1.0 (9 correct, 0 wrong), interpretation 0.82, 669 model calls. Whole-task completion needs all 3 files correct, so expected F_LM completion is near 0: verdict_with_tool NO_GAIN expected; verdict_model_off NO_GAIN expected. Wrong placements expected near 0 for F_LM; S_LM may misplace.",
 "known_limits": ["7B model, 4-bit; single prompt version; no retries", "excerpt choice is a fixed ATANOR rule",
                  "search entry points remain Wikimedia/Wiby/direct pages", "accepted names are single Wikidata labels"]}
(A / 'protocol_p7.json').write_text(json.dumps(proto, indent=2, ensure_ascii=False), encoding='utf-8')
d = A / 'DECISIONS.md'; t = d.read_text(encoding='utf-8').rstrip('\n')
t += '''
- 2026-10-24 · **P7 모델 설치(사용자 승인).** `qwen2.5:7b-instruct`(Ollama, 7.6B, Q4_K_M, Apache-2.0, digest `845dbda0ea48…697e`). 사용자의 기존 Ollama 저장소는 서버가 **모든 모델 manifest를 읽지 못하는 상태**("bad manifest: The system cannot find the path specified", 이전에 있던 모델들도 동일; 새 서버에서도 동일)여서, 사용자 앱은 건드리지 않고 실험용 서버를 **별도 포트 11435·별도 모델 폴더**(`runs/ollama/models`, git 무시)로 띄워 다시 받았다. 첫 시도에서 사용자 저장소에도 같은 모델 파일(4.7 GB)이 받아져 있다(사용자 앱에서는 보이지 않음). 진단 중 시험으로 만든 manifest 사본 1개는 지웠다.
- 2026-10-24 · **P7 dev 점검(모델 켬, H6 전이 세트·같은 ATANOR 상태)**: 채택 9 정답 / 0 오답(재현율 0.20, 정밀도 1.00), 근거 없음 15·단일 출처 12·모순 8; 올바른 문서에서 모델 1위 후보가 정답과 일치 8/44; 모델 호출 669회(입력 25.2만·출력 1.3만 토큰, GPU 134 s), 인용 검증 거부 191 / 수락 81. 모델 끈 같은 조건(H6)은 채택 0. ATANOR 쪽 검증 규칙 하나 추가: 확장자 자체(".dmg")를 이름 후보로 받지 않음(모델 역할 확대 아님). 원문 인용이 길게 들어갈 수 있는 모델 원응답은 로컬에만 두고(`results/**/model_calls*.jsonl` 무시), 공개 결과에는 파생 요약만.
- 2026-10-24 · **`protocol_p7.json` v1 동결(20:10).** 평가 문장 원본은 레포 밖, sha256 `4c7b67bb…b076`만 공개. 평가 형식 32개는 동결 공개 커밋 해시로 267개 풀에서 추첨. 조건 F_LM·S_LM·F·N·ORACLE, 판정 두 개(도구 포함 `verdict_with_tool`은 ATANOR+읽기 도구의 성과로만, 모델 끈 `verdict_model_off`만 ATANOR 학습 주장의 근거). **실행 전 기대: 둘 다 NO_GAIN**(과제 완수는 세 파일 모두 성공해야 함).'''
d.write_text(t + '\n', encoding='utf-8')
print('ok')
