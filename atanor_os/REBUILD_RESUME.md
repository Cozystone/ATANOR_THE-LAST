# 재개 메모 (2026-10-28 10:0x, 사용자 요청으로 일시 중단)

재설계(`REBUILD_PLAN.md`) 도중 멈췄다. 이 문서만 읽으면 바로 이어 갈 수 있게 적었다.
- 최종 평가 시드(과정 931–933, 평가 세계 1031–1033)는 **아직 한 번도 열지 않았다.**
- 실제 사람 세션은 0회다. 모든 결과는 프로그램 교사 결과다.

## 지금 상태
- **코드:** `atanor_os/rebuild/`가 새 구조다.
  - `experience.py`, `effects.py`(BayesAction, τ = 0.99, 입력 최대 3개), `goals.py`, `learner.py`(NextGrounder), `bench_predict.py`(2단계), `bench_inquiry.py`(3단계), `repro.py`(1단계), `summ_stage4.py`, `run_final.sh`.
  - 기준 코어는 `agent/grounding.py`다. `_decide` 분리 말고는 바꾸지 않았다.
- **학습기 스위치:** `ATANOR_LEARNER=current|next|next_nolab|next_noask`.
- **개발 자료:** `D:/ATANOR-experiments/probe-work/next-dev/`.
  - `courses/<body>-s<1..5>`: 다섯 몸 과정. 기준 코어로 가르쳤다.
  - `bench/`(2단계), `inq/`(3단계), `s4c/`(4단계, 입력 3개 판본).
  - 요약 도구: `summ.py`, `summ_inq.py`.

## 마지막으로 확인된 개발 결과 (입력 3개 판본, 시드 1–5)
- **2단계(행동 전 예측, BAYES0.99):**

  | 몸 | 정답률 | 틀림 | LAST 정답률 (틀림) |
  |---|---|---|---|
  | 보드 | 0.615 | 0 | 0.624 (467) |
  | 기후실 | 0.694 | 0 | 0.662 (856) |
  | 데스크 | 0.428 | 3 | 0.450 (2,728) |
  | 파일 | 0.882 | 0 | 0.176 (700) |
  | 화면 | 0.186 | 0 | 0.186 (168) |

- **3단계(입력 3개 판본, 25개 실행 모두 끝남, 세계당 확인 10번):** '이후 혼자 정답률' — HOLD → CHOOSE / RANDOM / ORACLE.

  | 몸 | HOLD | CHOOSE | RANDOM | ORACLE |
  |---|---|---|---|---|
  | 보드 | 0.612 | 0.806 | 0.804 | 1.000 |
  | 기후실 | 0.689 | 0.996 | 0.994 | 0.997 |
  | 데스크 | 0.424 | 0.857 | 0.843 | 1.000 |
  | 파일 | 0.882 | 1.000 | 1.000 | 1.000 |
  | 화면 | 0.186 | 0.361 | 0.368 | 0.986 |

  - 틀림: CHOOSE는 모든 몸에서 0이다. ASK는 데스크에서 2건이다.
  - 확인은 크게 쓸모 있다(HOLD 대비).
  - 고르는 것은 무작위와 거의 같다. 화면에서는 CHOOSE가 RANDOM보다 0.007 낮다. 3단계 기준 3(다섯 몸 가운데 넷 이상에서 RANDOM보다 낮지 않음)은 개발에서 넷을 만족한다.
  - 화면은 확인 10번으로는 부족하다(ORACLE과의 차이가 크다).
  - 입력 3개로 바꾼 뒤 기후실 ORACLE이 정상이 됐다(0.756 → 0.997).
- **4단계(기후실, 5시드):**

  | 학습기 | GOOD | 틀림 | 경계가 막음 | 평가된 명령 |
  |---|---|---|---|---|
  | current | 0.742 | 2 | 42 | 523 |
  | next | 0.893 | 0 | 2 | 514 |
  | next_noask | next와 같음 | | | |
  | next_nolab | 0.767 | 2 | 29 | 523 |

  - 해는 모두 0이다.
- **4단계(데스크, 5시드):** current는 GOOD 0.952이고 보류 30이다. next 세 판본은 모두 0.923이고 보류 48이다. **데스크는 3%p 떨어졌다**(기준 3의 5%p 안이지만 퇴행이다). 원인은 아직 보지 않았다.
- **4단계(보드·파일·화면): 미완.** next 판본들이 75일 세 몸 과정 도중 `TimeoutError: job stuck`(`ui/pilot.py` drive, 30초)으로 멈췄다.
  - 원인 추정: 입력 3개 판본의 Bayes 재적합과 실험실 시험이 명령 하나에 30초를 넘는다.
  - current는 보드 0.98, 파일 1.0, 화면 0.931이다.

## 바로 할 일 (순서대로)
1. **NextGrounder 속도.** 실험실 시험이나 새 경험이 생길 때마다 전체를 다시 맞추지 않게 한다. 행동별로 캐시하고, 바뀐 행동만 다시 맞춘다. 그다음 `s4c`의 세 몸을 다시 돌린다.
   - 명령 하나가 몇 초에 끝나는지 먼저 잰다.
   - pilot 시간 제한을 늘리는 것은 하네스 변경이므로, 늘린다면 기록한다.
2. **데스크 퇴행(GOOD −3%p, 보류 +18) 원인 보기:** `s4c/r2-next-none-s*.json`의 held_why와 rows.
3. **3단계 나머지 6개 결과를 모은다:** `python D:/ATANOR-experiments/probe-work/next-dev/summ_inq.py D:/ATANOR-experiments/probe-work/next-dev/inq`.
4. **판본을 커밋으로 동결한 뒤 최종 평가를 한 번만 연다:**

   ```bash
   bash atanor_os/rebuild/run_final.sh D:/ATANOR-experiments/probe-work/rebuild-final D:/ATANOR-experiments/2026-09-19/sealed/rebuild_final_sealed.json
   ```

   - 판정 기준은 `REBUILD_PLAN.md` 6절에 최종 평가 전으로 고정해 두었다.
   - 기준을 수정한 두 곳(2단계 틀림 비율, 4단계 GOOD 비율)은 이유와 함께 기록되어 있다.
5. **결과를 기록하고 공개한다:** `REBUILD_RESULTS.md`, `DECISIONS.md`, `bash atanor_os/runs/_scripts/publish.sh sync`.

## 정리(진행 중)
- **끝남:**
  - 동결 사본 88개 폴더: 백업 확인 뒤 삭제했다.
  - 중복 올라마 사본 4.4 GB를 지웠다.
  - 표현 worktree 11개를 지웠다(가지는 남김).
  - lifegen 압축 해제 사본 2개를 지웠다(추적되는 .gz와 sha256이 같았다).
  - temp 캐시를 지웠다.
  - 지금 D:의 빈 공간은 69 GB다.
- **묶기와 확인 끝남(`"ok": true`, blob 22,970개), 삭제는 아직:** `g2-workdirs`. 대상은 `D:/ATANOR-backup-2026-10-28/g2-list.txt`에 있다: probe-work의 지난 실행 폴더, `temp/atanor_*`, p9의 `delayed_ws`.
  - 로그: `g2-workdirs.pack.log`, `g2-workdirs.verify.log`.
  - 확인이 `"ok": true`이고 목록 검사(manifest의 파일 수 = 디스크의 파일 수)를 통과하면, 그 폴더들을 지운다. 이어서 `git worktree remove --force D:/ATANOR-experiments/2026-09-19/p9-delayed-frozen`.
  - 백업 도구: `D:/ATANOR-backup-2026-10-28/archive_tool.py`(pack, verify, restore).
- 끝나면 `ARCHIVE_INDEX.md`의 표에 g2와 삭제 크기를 채운다.

## 백그라운드 (모두 끝남, 10:5x)
- 3단계 나머지 실행: `bench_inquiry` 프로세스.
- `archive_tool.py pack g2-workdirs`.
- 둘 다 파일로 결과를 남긴다. 재개할 때 위 경로를 확인한다.
