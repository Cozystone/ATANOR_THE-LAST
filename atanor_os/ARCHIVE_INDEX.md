# 정리 기록 (2026-10-28)

`REBUILD_PLAN.md`를 시작하며 작업 공간과 저장소를 정리했다. 원칙은 다음과 같다.
- 삭제 전에 저장소 밖에 복구할 수 있는 백업을 만들고, 무결성을 확인했다.
- 공개 Git 기록은 다시 쓰지 않았다.
- 실패 기록은 지우지 않았다.

## 백업 (저장소 밖, 공개하지 않음: 일부 폴더에 웹 원문이 있을 수 있다)
위치: `D:/ATANOR-backup-2026-10-28/`

| 파일 | 담긴 것 | 무결성 |
|---|---|---|
| `repo-all-refs.bundle` | 개발 저장소의 모든 가지·태그(44개 참조). 지운 코드 파일은 모두 여기와 커밋 e7c4f12c에 있다 | `git bundle verify` 통과 |
| `g1-snapshots.tar.zst` + `.manifest.jsonl` | `2026-09-19/` 아래 동결 사본 전부(`snap*`, `gen1-frozen`, `gen1-closeout`, `gen2-closeout`). 내용이 같은 파일은 한 번만 담고, 목록이 원래 경로를 모두 기억한다 | 아래 표 |
| `archive_tool.py` | 묶기·확인·되살리기 도구 | 작은 사본으로 왕복 시험: 되살린 폴더가 원본과 바이트 단위로 같았다 |

되살리기:

```
python D:/ATANOR-backup-2026-10-28/archive_tool.py restore <archive> <dest_root> [path_prefix]
```

## 남긴 것
- **기준 코어:** `atanor_os/agent/grounding.py`(1세대 마감 코어 + G + H1, 동결 g58과 같은 동작). `learners.py`로 스위치(`core`, `core_m`, `g57`)를 고른다.
- **새 구조:** `atanor_os/rebuild/`.
- **몸 어댑터:** `world/` 다섯 몸과 web.
- **교수 UI:** `ui/teach_server.py`, `teach.html`, `pilot.py`, `session_report.py`.
- **교사·평가기:** `teach/tutor.py`, `teacher_policy.py`, `long_course.py`, `eval/clime_*`, `desk_eval2*`, `teacher_eval.py`, `tutor_life.py`.
- **권한 경계와 저널:** 몸의 실행 경계, `core/journal.py`.
- **오프라인 사례 묶음:** `repr/`(bundles, run_act, run_act6, run_bundles).
- **기록:** 모든 프로토콜과 결과 문서, `DECISIONS.md`, `results/`(추적되는 결과 전부).
- **봉인 세트:** `D:/ATANOR-experiments/2026-09-19/sealed/`. 저장소 밖에 그대로 있다. `gen4b2_sealed.json`은 만들었지만 쓰지 않았다(B2가 재설계 지시로 대체됨).
- **사용자 데이터:** `atanor/`(바탕화면 테마 스크립트, 추적 안 함), `user-sandbox/`, `backup/`(이전 공개 기록 묶음), `ATANOR_THE-LAST/`(공개 거울).
- **다른 작업:** `2026-10-27/trackA`(커밋하지 않은 바뀜 3개). 다른 작업이라 손대지 않았다.
- **남긴 부스러기:** `evidence/`의 SQLite `-wal`/`-shm` 파일. 지우거나 합치면 추적되는 증거 파일의 내용이 바뀐다.

## 지운 것
| 대상 | 크기 | 왜 지워도 되는가 | 되살리는 곳 |
|---|---|---|---|
| `atanor_os/runs/ollama/models` | 4.4 GB | 올라마가 실제로 쓰는 `D:/ML-models/ollama-models`와 같은 내용이다. blob 6개의 sha256이 이름과 같고, manifest도 바이트 단위로 같다 | 실제 저장소 그 자체 |
| 학습기 동결 사본 `agent/grounding_g35`–`g44` (7개) | — | 현재 코드에 복사해 둔 이전 판본이다. 각 사본은 그 커밋에 있다 | 커밋 e7c4f12c, bundle |
| 쓰지 않는 모듈 46개와 그 테스트 13개 (P-시리즈 루프·planner·skills·supervisor, p6–p9·h6 평가기, lang, renderer, run_ask 등) | — | 현재 코어·평가기·UI·교사·rebuild에서 import 경로가 닿지 않는다(함수 안 import까지 따라감) | 커밋 e7c4f12c, bundle |
| `2026-09-19/` 동결 사본 폴더 | 아래 표 | 코드는 커밋으로, 그 밖의 파일은 `g1-snapshots`로 되살린다 | `g1-snapshots.tar.zst` |

테스트: 지운 뒤 `pytest atanor_os/tests` 결과는 71 통과, 1 xfail이다(지우기 전에는 121 통과였고, 그 차이는 지운 테스트들이다).
기준 코어의 `_decide` 분리(행동 대상 결정을 함수 하나로 옮김)는 동작을 바꾸지 않았다. 기후실 시드 1 과정의 로그와 사건이 바이트 단위로 같았다.
