# P4 on the HP laptop: spec tests, process-level crash test, 200-episode long run with online learning.
# Runs detached (launched through Win32_Process Create; the laptop has no cmd.exe). Writes everything under runs\.
$py = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
Set-Location C:\Users\test\ATANOR\dev3
New-Item -ItemType Directory -Force runs | Out-Null
"start $(Get-Date -Format o)" | Out-File runs\p4_status.txt
& $py -m pytest atanor_os/tests -q -p no:cacheprovider 2>&1 | Out-File runs\p4_tests.txt
"tests done $(Get-Date -Format o)" | Add-Content runs\p4_status.txt
& $py -m atanor_os crash --root runs\p4_crash_hp --body fs --experiences experiences_s1.jsonl --episodes 40 --kill-min 0.5 --kill-max 3.0 --seed 1 --max-restarts 300 2>&1 | Out-File runs\p4_crash_hp.txt
"crash done $(Get-Date -Format o)" | Add-Content runs\p4_status.txt
& $py -m atanor_os supervise --root runs\p4_long_hp --body fs --experiences experiences_s1.jsonl --episodes 200 2>&1 | Out-File runs\p4_long_hp.txt
"long done $(Get-Date -Format o)" | Add-Content runs\p4_status.txt
& $py -m atanor_os supervise --root runs\p4_long_hp_view --body view --experiences experiences_view_s1.jsonl --episodes 100 2>&1 | Out-File runs\p4_long_hp_view.txt
"all done $(Get-Date -Format o)" | Add-Content runs\p4_status.txt
