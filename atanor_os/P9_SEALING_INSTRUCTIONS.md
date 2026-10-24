# P9 봉인 문장 작성 지시 (공개, 2026-10-24)

평가 문장은 교사 문맥을 받지 않은 별도 에이전트가 썼다. 아래 지시는 교사(이 세션의 Claude)가 썼다.

교사는 지시에 표현의 예시를 적었다(동사·유형 이름). 이를 감안해 훈련 문장은 그 예시 동사와 유형 표현을 쓰지 않았다(`teach/p9_sentences.py`의 머리말 참고). 지시 원문을 아래에 그대로 둔다. 평가 문장 원본은 실행 전에 열지 않았고, 실행 후 공개한다.

---

> You are writing a sealed evaluation set for a research experiment. Do NOT read any files in D:\ATANOR-experiments\2026-09-19\developmental-research or D:\ATANOR-experiments\2026-09-19\ATANOR_THE-LAST (you must stay independent of the system being tested). Only write the two files below.
>
> Task: write English one-sentence commands that a person might give to an assistant managing a folder of files. Each command does ONE of three things to a group of files:
> - copy them into a new folder (originals stay),
> - move them into a new folder (originals go away),
> - delete them.
>
> The group of files is described only by file type (extension) or as all files. Allowed extensions: txt, csv, md, log, json. Never mention specific file names, counts, sizes, dates, or folders that already exist. For copy and move, the destination is a NEW folder whose name is a single plain lowercase English word (letters only, 3-9 letters, not a file extension, not one of: copy, move, delete, file, files, folder). State the destination name explicitly in the sentence. Delete commands have no destination.
>
> Write naturally and with variety, as different people would phrase it: vary verbs (e.g. duplicate, back up, relocate, shift, put, stash, remove, erase, get rid of, trash...), vary how file types are named (".csv files", "CSV spreadsheets", "markdown files", "the logs", "text files", "JSON files", "anything ending in .md", "all the files", "everything"...), vary sentence structure and politeness. Every sentence must still have exactly one correct reading.
>
> Make two files, each a JSON list of 30 objects:
>   {"id": "<set>-NN", "sentence": "...", "tool": "copy"|"move"|"delete", "ext": "txt"|"csv"|"md"|"log"|"json"|"any", "dest": "<name>" or null}
> ("ext": "any" means all files.) In each set: 10 copy, 10 move, 10 delete; about 12 sentences using txt/csv/md, about 12 using log/json, about 6 using all files. The two sets must contain different sentences and different destination names.
>
> Files (create the folder if needed):
>   D:\ATANOR-experiments\2026-09-19\sealed\p9_immediate.json   (ids "imm-01".."imm-30")
>   D:\ATANOR-experiments\2026-09-19\sealed\p9_delayed.json     (ids "del-01".."del-30")
> Write them as UTF-8 JSON. Check each file parses and has 30 items with the required counts.
>
> Then compute the sha256 of each file (e.g. with PowerShell Get-FileHash or Python hashlib) and reply with ONLY: the two full sha256 hex digests, and the per-set counts (tool counts and ext counts). Do NOT include any sentence text, destination names or other content of the files in your reply.

---

작성 에이전트의 회신은 해시와 개수뿐이었다(문장 내용 없음).
- 즉시 세트 sha256 `882942f8f464678f632c578e9b3d2c7dfc00be02fd24f6b38f471d5a48b361e6`
- 지연 세트 sha256 `3386e118204511e6e3f8cc360f3642a3aaee8a95df61cd465828a026d4682e78`

두 세트의 구성은 같다: copy·move·delete 각 10, 확장자 txt 4 · csv 4 · md 4 · log 6 · json 6 · 전부 6. 교사가 해시를 다시 계산해 일치를 확인했다.
