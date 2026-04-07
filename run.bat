@echo off
chcp 65001 >nul
echo ============================================
echo   arXiv 论文追踪与智能总结系统
echo   运行时间: %date% %time%
echo ============================================
echo.

:: 激活 conda 环境（请根据你的 conda 安装路径调整）
call conda activate arxiv_tracker

:: 切换到项目目录（请修改为你的实际路径）
cd /d "%~dp0"

:: 检查今天是否是周日
for /f "tokens=1" %%a in ('python -c "from datetime import datetime; print(datetime.now().weekday())"') do set DOW=%%a

if "%DOW%"=="6" (
    echo [INFO] 今天是周日，系统休息，不执行任何操作。
    echo.
    goto :END
)

:: 步骤1：抓取 arXiv 论文
echo [步骤1/2] 正在从 arXiv 抓取最新论文...
echo.
python fetch_papers.py
if errorlevel 1 (
    echo [ERROR] 论文抓取失败！请检查网络连接和配置文件。
    goto :END
)
echo.
echo [步骤1/2] 论文抓取完成！
echo.

:: 步骤2：LLM 智能总结
echo [步骤2/2] 正在调用大模型进行论文总结...
echo.
python llm_summarize.py
if errorlevel 1 (
    echo [ERROR] LLM 总结失败！请检查 API 配置。
    goto :END
)
echo.
echo [步骤2/2] LLM 总结完成！
echo.

echo ============================================
echo   全部流程执行完毕！
echo   请查看 output 目录获取结果文件。
echo ============================================

:END
echo.
pause
