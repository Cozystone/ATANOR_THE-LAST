# View-body pilot replication on the HP laptop (label replication-hp: not a judgement run). Same snapshot code
# as results/p3-view-01 (sha 6ac1457be2fcf22c), same protocol, seeds, tasks, steps and policy.
$py = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
Set-Location C:\Users\test\ATANOR\dev4
New-Item -ItemType Directory -Force runs | Out-Null
"start $(Get-Date -Format o)" | Out-File runs\view_status.txt
& $py -m atanor_os pilot --body view --split test --seeds 1,2,3,4,5 --tasks 20 --steps 600 --conditions A,B,C --policy contrast-kind --label replication-hp --out runs\p3-view-hp 2>&1 | Out-File runs\view_pilot.txt
"done $(Get-Date -Format o)" | Add-Content runs\view_status.txt
