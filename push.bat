@echo off
cd /d C:\matteus-data
git add -A
git commit -m "question maker update"
git pull --rebase
git push
echo.
echo Done. If you see an error above, take a screenshot and show it to Claude.
pause
