# ATANOR OS v0 — 이식 감사 (port audit)

2026-10-24. 읽기 전용 감사. 소스 변경 없음. 실행한 것은 기존 테스트 2개 파일뿐.
대상: 이 저장소의 Whole Mind V0(`a812362`)를 HP Pavilion 15(i7-6700HQ / GTX 950M / 16 GB)
한 대에 "지속적으로 살아가는 runtime"으로 이식하기 위한 사전 조사.
Brief: "ATANOR OS = A persistent developmental runtime for one artificial Self."

## 0. 한 줄 결론

봉인된 cognition은 온전하고 이 PC에서 그대로 실행된다. 8개 frozen 파일을 건드리지
않고 Linux로 옮길 수 있다. 다만 (1) runtime의 불변식 다섯 가지가 "OS v0"의 모양을
강하게 제약하고, (2) brief가 가정한 것보다 무거운 의존성 하나(torch)가 frozen 경로에
붙어 있으며, (3) brief §5의 Body 목록 중 clock/terminal/process는 권위 있는 경로에
존재하지 않는다. 결정이 필요한 지점은 §7에 모았다.

## 1. Brief §1 순서대로 확인한 사실

| 항목 | 결과 |
|---|---|
| 저장소 | `D:/ATANOR-experiments/2026-09-19/developmental-research` 존재. `D:/ATANOR-experiments/2026-09-13/shared-world-core`의 git worktree (13개 worktree 중 하나) |
| branch / HEAD | `codex/whole-mind-integration`, HEAD = `a812362` (2026-09-20), 193 commits |
| 기준 commit | `a890256` (frozen cognition), `f112616` (protocol/preflight), `a812362` (final validation) 모두 존재 |
| remote | **없음.** 이 디스크 한 곳에만 존재하는 단일 사본 |
| 작업 트리 | 깨끗함. untracked는 `evidence/developmental-directory-acquisition-v1/*.sqlite-shm/-wal` 4개뿐 (무관) |
| `ATANOR_WHOLE_MIND_V0_VALIDATION.md` | 읽음. 판정 `WHOLE_MIND_V0_VALID_CAPABILITY_FAIL` |
| `evidence/whole-mind-v0-valid/FINAL_STATUS.json` | 읽음. `source_unchanged: true`, `extra_native_actions: 0`, arm별 7/8, 1/8, 2/8 |
| `evidence/whole-mind-v0-valid/` | full / no_memory / no_planning 각각 `world.sqlite`, `journal.json`, `thoughts.jsonl`, `receipt.json`, `intervention.json`, `preview_before/after.json`, `final_native_state.json`, `pre_finalization/` 보존. `PREFLIGHT.json`, `DISTURBANCE_PREFLIGHT.json`, `TRIAL_STARTED`, `FINALIZATION_COMPLETED` 존재 |
| frozen 8개 파일 해시 | **현재 sha256이 `FINAL_STATUS.hashes_after`와 전부 일치.** 봉인 이후 변경 없음 |
| 실행 확인 | `tests/test_whole_mind_bridge.py`, `tests/test_whole_mind_valid_eval.py` → 10 passed (3.4 s). Python 3.13.12, numpy 2.4.6, torch 2.11.0+cu128 |

Whole Mind 관련 파일 (evidence 제외):
`scripts/whole_mind_bridge.py`(130줄), `whole_mind_mission.py`(110), `whole_mind_valid_worker.py`(63),
`whole_mind_valid_eval.py`(244), `whole_mind_valid_finalize.py`(94), `persistent_mind_loop.py`(102);
`docs/ATANOR_WHOLE_MIND_MAP.md`, `WHOLE_MIND_STATE.md`, `ATANOR_WHOLE_MIND_V0_{EXECUTION,FINAL,VALIDATION}.md`,
`ATANOR_WHOLE_MIND_VALIDATION_PREREG.md`.

## 2. 기존 시스템의 실제 구조

### 2.1 프로세스 모양 (V0 검증 당시)

```
whole_mind_valid_eval.py  (evaluator; cognition이 import하지 않음)
  └─ subprocess: whole_mind_valid_worker.py <folder> <intent-digest> first
        Sandbox(root, **cfg)            ← body (실제 임시 디렉터리)
        WholeMindClient(...)            ← cognition (H plan_agent + DictStore)
        WorldSession(world.sqlite, body, client, ...)   ← world + journal + 권위
        issue_goal → step ×5 → stdin 'external-event-done' 대기 → 종료
  └─ evaluator가 n7을 외부에서 FILE로 강제 (학습자 밖의 사건)
  └─ subprocess: ... resume
        Sandbox.attach(root, ...)       ← 같은 몸을 다시 붙임
        WorldSession(같은 world.sqlite) ← journal 검증 후 client.restore(model)
        poll('restart_reobservation') → step ... → GOAL_END
  └─ verify_world(...)                 ← 처음부터 native 재실행으로 독립 검증
```

한 번의 "깨어남" = 프로세스 하나. 지속성은 전부 `world.sqlite` 하나에 있다.

### 2.2 Brief의 여섯 기관 ↔ 현재 코드

| Brief §5 | 현재 존재 형태 | 위치 |
|---|---|---|
| **Self** | `self_id` 문자열 하나. 객체/생성시각/lifetime 없음. binding에 고정됨 | `runtime.py:156-166` |
| **World** | `WorldSession._state` checkpoint(`state` 테이블) + 실제 디스크(`Sandbox`). 권위는 항상 디스크 재관측(`_actual`) | `runtime.py:145-227`, `world.py:264-288` |
| **Journal** | `events(seq, kind, payload, digest)` SHA-256 체인. 12종 이벤트 | `runtime.py:70-83`, `215-227` |
| **Cognition** | `WholeMindClient` → H 포팅판 `plan_agent` + `DictStore` 메모리. 모델 상태는 `client.snapshot()`으로 world checkpoint 안에 저장 | `whole_mind_bridge.py:53-130`, `historical_goal_world.py` |
| **Body** | `Sandbox`: 선언된 핸들 `n0..nk`, 종류 0/1/2(absent/file/dir), 연산 `mkdir/empty/unlink`(+ `copy/rename`은 schema에만) | `world.py:111-305`, `schema.py` |
| **Supervisor** | **상주 프로세스 없음.** evaluator 스크립트가 phase마다 worker를 띄움 | `whole_mind_valid_eval.py:150-171` |

### 2.3 Journal 이벤트 ↔ brief §5 Journal 목록

| Brief | 실제 kind | 비고 |
|---|---|---|
| OBSERVATION | `BEGIN`(초기), `OBSERVE`, `SENSE` | `reason`: poll / pre_decision / changed_during_decision / goal_end / restart_reobservation |
| PREDICTION | `PREDICT` | 학습자 forecast. 완료 증거로 절대 쓰이지 않음 (`_complete`, `runtime.py:34-49`) |
| ACTION INTENT | `DECIDE` + `DISPATCH` | DISPATCH 직후 `body.step` |
| ACTION RESULT | `RESULT` | 디스크 재관측. `succeeded` 플래그 |
| (학습) | `LEARN` | 모델 digest/revision 전진 |
| EXTERNAL EVENT | **전용 kind 없음.** `OBSERVE`에 `changed: true`로만 나타남 | 원인은 journal 밖(`intervention.json`). `verify_world`는 외부 사건 스케줄을 따로 받아야 재실행 가능 (`runtime.py:396-402`) |
| GOAL STATE / END | `GOAL`, `GOAL_END` | `reason`: goal_reached / step_budget_exceeded / decision_budget_exceeded / policy_abstained / invalid_proposal / no_valid_actions |
| (정지) | `HALT`, `INTERRUPTED` | §2.4 참조 |

관측·예측·믿음·실제 결과의 분리는 brief 요구대로 이미 되어 있다. "믿음"은 journal에
진실로 기록되지 않고 client model(checkpoint의 `model`) 안에만 있다.

### 2.4 OS 이식을 좌우하는 불변식 (코드에 박혀 있고, 바꾸면 frozen 위반)

1. **몸의 정확한 타입.** `_validate_body`: `type(body) is Sandbox` 아니면 거부 (`runtime.py:52-54`). `verify_world`도 `Sandbox`를 직접 생성 (`:420`). 새 body 클래스는 권위 경로에 못 들어온다.
2. **루트는 임시 디렉터리 아래.** 새 몸: `root`가 `tempfile.gettempdir()` 아래의 새 자식이어야 함 (`world.py:163-166`). 재부착: 그 아래의 기존 디렉터리 (`:131-134`). → Linux에서 `/tmp`는 보통 tmpfs(재부팅 시 소멸). **`TMPDIR` 환경변수로 `/home/atanor/world` 같은 영속 경로를 지정하면 소스 변경 없이 통과한다.** Supervisor unit이 이 변수를 책임져야 한다.
3. **binding 불변.** config(paths/protected/operations), `total_budget`, `decision_cap`, `world_id`, `self_id`는 `BEGIN`에 고정되고 재개 시 하나라도 다르면 `resume_external_binding_mismatch` (`runtime.py:180-181`). 예산을 나중에 늘릴 수 없다.
4. **평생 예산.** `total_budget`은 goal 하나가 아니라 **world 전체의 step 상한** (`runtime.py:307-311`). `decision_cap` 기본값 `max(16, 4×budget)`. 다 쓰면 그 world에서는 더 이상 행동 불가. 반면 goal은 끝난 뒤 새 id로 계속 발급 가능 (`issue_goal`, `:242-253`).
5. **중단은 영구 정지.** 재개 시 `pending`이 남아 있으면(`DISPATCH`~`LEARN` 사이에 죽음) `INTERRUPTED`를 기록하고 `halted='pending_interrupted'` (`:182-185`). 이후 `step()`은 영원히 `{'halted': ...}` (`:297-298`). `learner_update_failed`도 영구 `HALT` (`:373-375`). **halted를 푸는 경로는 없다** — 설계 의도("Pending recovery is safe stopping", `:401-402`).
6. **슬롯 고정.** 핸들 집합은 생성 시 선언되고 늘지 않는다. ATANOR는 "새 파일을 만들" 수 없고 선언된 슬롯의 종류만 바꾼다. `sense()`는 관측 범위만 넓힌다 (`:255-275`).
7. **열 때마다 전체 검증.** `_read` + `_check_resume_state`가 journal 전체를 재생해 checkpoint와 대조 (`:70-142`). 불일치 → 열기 거부. 복구 경로 없음(의도적).
8. **checkpoint가 매 이벤트 통째로 다시 쓰임.** `_record`가 `canonical(state)` 전체를 `INSERT OR REPLACE` (`:221-225`). 그 state에는 `model`이 포함되고, bridge의 `learn`은 **모든 사건을 `records`에 영구 추가** (`whole_mind_bridge.py:123-130`, 상한 없음; `history`만 256 제한). → 이벤트당 쓰기 비용이 선형 증가, 누적 O(n²). 며칠짜리 삶 하나를 world 하나에 담으면 수천 step 근처에서 I/O가 지배한다.
9. **Bridge의 의미론 한계.** 단항 연산만 (`:57-58`), 평평한 frame만(parent/relations 있으면 거부, `:38-41`, `:81-82`), kind-only goal만 (`:92-93`). RNG는 `410927 + revision`으로 결정적 (`:98`).
10. **관측은 supervisor만.** 학습자는 `Frame` 사본만 받고 `evidence()`(sha256/size)는 절대 못 본다 (`runtime.py:29-31`, `world.py:276-288`).

### 2.5 Mission/intent 형식 (재사용 가능)

`intent.json` = `{config: encode_config(cfg), body_root, arm, goal: Goal.to_dict(), cap}`.
`cfg = {paths: [...], initial: {path: bytes|None}, protected: ['n8'], operations: [{id, arity}]}`.
`Goal(id, kinds=((handle, 0|1|2), ...))` (`planner.py:15-104`). 바이트 값은 hex 인코딩
(`persistent_mind_loop.decode_config`). 원시 전이표는 `PREFLIGHT.json`의
`native_transition_checks`에 9행으로 측정되어 있다 (예: absent+mkdir→dir, dir+unlink→dir 실패).

## 3. 그대로 가져가는 부분

- frozen 8개 파일 + 그 import 대상(`relations.py`, `observation_scope.py`, `model.py`, `schema.py`). 순수 Python. 내부 경로는 `PurePosixPath`. Windows 전용 코드는 전부 guard됨(`st_file_attributes` getattr, 예약 장치명 검사는 Linux에서 무해). 최소 Python 3.9(`is_relative_to`); 검증 환경 3.13.
- `Sandbox` = v0 Body (brief의 "sandboxed filesystem" 그대로).
- `WorldSession` = World + Journal + 권위 + 재개.
- `WholeMindClient` = Cognition. 모델은 world checkpoint에 실려 재개 시 복원됨 (`runtime.py:187`).
- worker 패턴(깨어남 1회 = 프로세스 1개, `intent` digest 바인딩) = Supervisor 자식의 모양.
- `verify_world` = 부팅 시 "durable state integrity check"로 쓸 수 있는 독립 검증기. 단, 외부 사건 스케줄이 필요하고 journal 길이에 비례해 느려진다.

## 4. 없는 것 — OS 층에서 새로 써야 하지만 cognition은 아닌 것

| 필요 | 현재 | 최소 구현 (frozen 파일 무변경) |
|---|---|---|
| Supervisor 상주 | 없음 | systemd unit → 무결성 검사 → worker 1개 spawn → 종료 신호 시 **step 경계에서** 멈춤 → lifecycle 기록. 역할은 보존·기동·검증·격리뿐 |
| Self 기록 | `self_id` 문자열 | supervisor 소유 `self.json`: id, 생성시각, 지나온 world DB 계보, 마지막 model digest |
| 삶 = world 체인 | world 1개 = 예산 1개 | 예산 소진·INTERRUPTED·HALT 시 **새 `world-NNNN.sqlite`**를 같은 `self_id`로 열고, 직전 checkpoint의 `model.records`를 새 `WholeMindClient(records, ...)`에 넘김. 체인 자체는 supervisor가 journal한다 (runtime 밖) |
| Goal 공급 | evaluator가 하나 저작 | goal 없으면 `step()`은 `{'idle': True}`. v0는 **운영자가 저작한 standing goal 목록**이 필요하다. 자율 목표 생성은 brief가 금지 |
| 외부 사건 기록 | journal 밖 `intervention.json` | supervisor가 자기 로그에 "내가 세계를 건드렸다"를 남긴다. ATANOR 쪽에는 그대로 `OBSERVE changed=true`로만 보인다 (올바른 분리) |
| 깨끗한 종료 | stdin 핸드셰이크 | worker가 매 `step()` 뒤 stop 플래그 확인. 전원 차단은 어쩔 수 없이 INTERRUPTED → 다음 world로 계보 이어짐 |
| clock / terminal / process body | **권위 경로에 없음.** 시간은 journal payload의 `observed_at_ns`에만 있고 학습자는 못 본다 | v0는 몸 = `Sandbox`만. 다른 adapter는 (a) 권위 밖의 별도 관측으로 두거나 (b) runtime 변경(금지) |

## 5. 의존성

| 구분 | 내용 |
|---|---|
| Python | ≥3.9. 검증 3.13.12. **Debian 13 (trixie)가 3.13을 기본 제공** → 동일성 확보에 가장 좋음. Ubuntu 24.04는 3.12 |
| 표준 라이브러리 | sqlite3(WAL, `synchronous=FULL`), tempfile, hashlib, json, pathlib |
| numpy | `whole_mind_bridge.py`, `planner.py`, `historical_goal_world.py`. RNG 결정성이 numpy `Generator` 구현에 의존 → 같은 major로 고정 권장 (여기 2.4.6) |
| **torch** | **frozen 경로가 import한다.** `planner.py:11 → model.py:16-18`, `episode.py:16 → model.Forecast`. Whole Mind 결정은 신경망을 호출하지 않지만 import는 피할 수 없다. CPU 휠(수백 MB)로 충분, GPU 불필요. shim은 frozen 2개 파일을 건드리므로 v0에서는 하지 않는다 |
| 불필요 | pywin32, pynvml, colorama, dill, tqdm (이 PC의 torch 부속). H 저장소(`C:/0.ASKIM ALL-VIN/27., ATANOR DEMO`)도 불필요 — `historical_goal_world.py`는 R 자체 포팅판 |
| 잠복 위험 | `historical_goal_world.py`가 `.construction_mind`, `.machine_shop`, `.grounded_language`를 지연 import (`:615, 731, 1178, 1258, 1372`)하는데 **이 저장소에 그 모듈이 없다.** bridge 경로는 도달하지 않음(테스트 통과). 다른 진입점을 열면 ImportError |
| 저장소 보존 | remote 없음 → 이식 전에 `git bundle` 또는 bare clone으로 사본을 하나 더 만들 것 (push 아님, 로컬 사본) |

## 6. HP 노트북 — 읽기 전용 점검 결과와 Linux 설치 전 체크리스트

### 6.1 확인된 하드웨어 → Linux 드라이버

| 부품 | 식별 | Linux | 비고 |
|---|---|---|---|
| Wi-Fi/BT | Intel Dual Band Wireless-AC 3165 (`8086:3165`) | `iwlwifi` + `firmware-iwlwifi`(non-free-firmware) | 설치 매체에 펌웨어 포함 필요 (Debian 12+ 기본 포함) |
| 유선 | Realtek RTL8136 FE (`10ec:8136`) | `r8169` 내장 | 100 Mbps |
| 내장 GPU | Intel HD Graphics 530 | `i915` + Mesa, 완전 공개 | 화면 출력은 이쪽. v0는 이것만 쓴다 |
| 외장 GPU | NVIDIA GTX 950M (Optimus) | `nouveau` 또는 비공개 드라이버 | v0 불필요. 전력 때문에 runtime PM으로 꺼두는 편이 좋음 |
| 오디오 | Realtek HD Audio | `snd_hda_intel` | |
| 웹캠 | HP Truevision HD | `uvcvideo` | v0 불필요 |
| 저장 | Samsung 850 EVO M.2 250 GB SATA (9,142 h, Healthy); WD 1 TB HDD (9,095 h, 32 °C, Healthy) | | SSD에 Windows(C: 230 GB, 78 GB 남음). HDD = D: 931 GB 중 907 GB 비어 있음 |
| 배터리 | 완충 21,312 mWh, 설계값 읽히지 않음 | | 이 급의 원래 팩보다 작게 보임(수명 저하 추정). 상시 전원 연결 전제 |
| 펌웨어 | BIOS F.78. `PEFirmwareType` 비어 있음, `Confirm-SecureBootUEFI` 미지원 오류, 두 디스크 모두 **MBR**, EFI 파티션 없음 | | **Legacy/CSM 부팅으로 추정.** `bcdedit`로 확정 필요(노트북 절전 중이라 미확인) |

### 6.2 백업 대상 (노트북 안)

| 위치 | 내용 | 크기 | 상태 |
|---|---|---|---|
| `C:\Users\ammen\Downloads` | 60 파일 | 1.41 GB | 백업 |
| `C:\Users\ammen\OneDrive` | 175 파일 (Desktop/Documents/Pictures가 여기로 리디렉션된 듯) | 0.5 GB | 클라우드 동기화 여부 확인 후 백업 |
| `C:\Users\ammen\{Videos,Music,Favorites}` | 소수 | ~0 | 백업 |
| `D:\` | `!!anNFq`, `20190515 … 69 …`(한글), `NaverCloud`, `SteamLibrary`, `Program Files`, 한글 폴더 1개 | **미측정** (절전으로 중단) | HDD는 설치에서 **건드리지 않음**이 기본 |
| AutoDesk AutoCAD 2024 | 계정 기반 라이선스 | — | 재설치 시 로그인으로 복구 |
| Windows 10 Home | 디지털 라이선스(보드 귀속) | — | 재설치 시 자동 재인증 |
| 이 PC의 저장소 | remote 없음 | — | §5 "저장소 보존" |

### 6.3 Windows 복구 가능성 확보

- **권장: Linux 설치 전에 SSD 전체 이미지를 HDD(D:)에 저장** (Clonezilla USB, 233 GB → 907 GB 여유). 파티션 4개(C:, 복구 0.9 GB ×2, AOMEI 0.8 GB)를 통째로 담으면 되돌리기는 이미지 복원 한 번.
- E: `ESD-USB`는 **Windows 11 24H2** 설치 매체다. Windows 10으로 돌아가려면 Win10 ISO가 따로 필요하거나 위 이미지가 있어야 한다.
- HDD(D:)를 설치 대상에서 제외하면 D:의 개인 자료는 그대로 남는다.

### 6.4 설치 계획 (초안, brief §7)

1. 노트북 깨워서 §6.1 펌웨어 확인(`bcdedit`), §6.2 D: 크기 측정, Windows 라이선스 상태 기록.
2. 백업: ammen 사용자 자료 → 외부/다른 PC. SSD 이미지 → D:.
3. BIOS(F10): **UEFI 모드 켜고 Legacy Support 끄기**, Secure Boot 끄기(nouveau/펌웨어 단순화), 부팅 메뉴 F9. 선택: 950M을 BIOS에서 끌 수 있으면 끈다.
4. 매체: **Debian 13 netinst (amd64, non-free firmware 포함판)** → 이 PC에서 USB 제작(E: USB 재사용 시 명함 PDF 2개 먼저 백업).
5. 파티션: **SSD만**, GPT, `/boot/efi` 512 MB + `/` ext4 나머지 + swap 8 GB. **HDD 미접촉.**
6. 첫 부팅 후(노트북 앞에서): 유선/무선 연결, sshd, 운영자 계정에 이 PC의 키 등록. 이후 전부 원격.
7. 계정/격리: `atanor` 시스템 사용자(sudo 없음, 쉘 없음), `/home/atanor/{world,memory,workspace}` 소유, 다른 홈 접근 불가. 네트워크는 uid 기준 기본 차단(nftables) 또는 unit의 `PrivateNetwork=`.
8. 런타임: Python 3.13 venv, `numpy` + `torch`(CPU) + 저장소 사본. unit에 `Environment=TMPDIR=/home/atanor/world`.
9. suspend/resume, 덮개 닫힘 무시(`HandleLidSwitch=ignore`), 전원 연결 시 절전 끔 — "켜져 있는 시간 = 살아 있는 시간"이 성립하려면 필수.

### 6.5 아직 못 한 것

노트북이 절전으로 응답하지 않음(ping 없음). 깨우면: `bcdedit` 부팅 모드, D: 폴더 크기, 사용자 자료 상세, 라이선스 상태, Linux live USB로 Wi-Fi/suspend 실측.

## 7. 결정이 필요한 지점 (brief와 기존 코드의 충돌) — 권고 포함

1. **삶 vs 예산.** world 하나는 `total_budget`으로 끝나고(§2.4-4) checkpoint 비용이 누적된다(§2.4-8). → **삶 = world DB의 체인**으로 정의. 한 world는 수백~수천 step 단위(예: `total_budget=2000`), supervisor가 체인과 model 승계를 기록. runtime 무변경.
2. **crash/재부팅 의미.** 코드는 중단을 영구 정지로 둔다(§2.4-5). 이것은 버그가 아니라 안전 정지다. → **"깨끗한 정지"를 step 경계에서 보장**(worker stop 플래그 + systemd `TimeoutStopSec`)하고, 전원 차단으로 INTERRUPTED가 나면 그 world를 닫고 다음 world로 같은 Self가 이어진다. "재부팅 = resume"은 **계보 수준**에서 성립하며, world 수준에서는 깨끗한 정지였을 때만 성립한다. brief §9 기준의 해석을 이렇게 고정할지 결정 필요.
3. **goal의 출처.** goal 없는 world는 idle이다. → 운영자가 저작한 standing goal 목록(예: 슬롯 8개의 목표 배치 몇 가지)을 순환 발급. 해법은 제공하지 않는다(brief §3). 자율 목표 생성 없음.
4. **몸의 범위.** 권위 있는 몸은 `Sandbox` 하나뿐(§2.4-1). brief §5의 clock/terminal/process는 v0에서 **제외**하고 시간은 journal 타임스탬프로 충족한 것으로 본다. 이걸 넣으려면 runtime을 열어야 하므로 v1 이후 연구 문제.
5. **torch.** frozen 경로의 import 의존(§5). → CPU 휠 설치로 해결, shim 금지.
6. **외부 사건 재현.** `verify_world`는 외부 사건 스케줄을 밖에서 받아야 한다(§2.3). 실제 노트북에서 "외부"는 운영자/OS뿐이므로 supervisor가 자기 개입을 전부 로그하면 재실행 검증이 유지된다. 단, 노트북에서 ATANOR 외의 프로세스가 `/home/atanor/world`를 건드리지 못하게 해야 한다(권한 §6.4-7).

## 8. 다음 순서 (brief §8 유지)

- [x] 1. 기존 코드·evidence 읽기 (이 문서)
- [x] 2. primitives·불변식 문서화 (§2.4)
- [ ] 3. 노트북 읽기 전용 점검 — §6.5 잔여분 (노트북 깨운 뒤)
- [ ] 4. 설치 계획·백업 체크리스트 확정 (§6.2–6.4 초안을 §7 결정과 함께 확정)
- [ ] 5–9. 설치 → 계정/격리/systemd → Sandbox+clock 연결 → Self/World/Journal 생성 → E2E 재부팅 테스트 → 반복 검증
- [ ] 10. 며칠간 실제 기록 수집 후 다음 연구 문제 선정

본 문서는 감사 기록이며 capability·성공 주장을 포함하지 않는다.
