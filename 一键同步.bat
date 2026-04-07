@echo off
chcp 65001 >nul
git add .
git commit -m "提交更新"
git remote set-url origin git@github.com:ScallopShark-ai/papercatch.git
git push origin main
pause