@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ================================================
echo   ติดตั้งโปรเจกต์ Jarvis อัตโนมัติ
echo ================================================
echo.

REM ----- ย้ายไปยังโฟลเดอร์ที่ไฟล์ .bat นี้อยู่ (โฟลเดอร์โปรเจกต์) -----
cd /d "%~dp0"
echo [1/6] ทำงานอยู่ที่โฟลเดอร์: %cd%
echo.

REM ----- เช็คว่ามี Python 3.11 ติดตั้งอยู่ในเครื่องหรือไม่ -----
echo [2/6] กำลังเช็คว่ามี Python 3.11 ติดตั้งอยู่หรือไม่...
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] ไม่พบ Python 3.11 ในเครื่อง
    echo กรุณาติดตั้ง Python 3.11 ก่อน จากลิงก์นี้:
    echo https://www.python.org/downloads/release/python-31115/
    echo อย่าลืมติ๊ก "Add python.exe to PATH" ตอนติดตั้ง
    echo.
    pause
    exit /b 1
)
echo       พบ Python 3.11 เรียบร้อย
echo.

REM ----- สร้าง virtual environment ถ้ายังไม่มี -----
echo [3/6] กำลังสร้าง virtual environment (venv)...
if exist "venv\" (
    echo       พบโฟลเดอร์ venv อยู่แล้ว ข้ามขั้นตอนนี้
) else (
    py -3.11 -m venv venv
    if errorlevel 1 (
        echo [ERROR] สร้าง venv ไม่สำเร็จ
        pause
        exit /b 1
    )
    echo       สร้าง venv สำเร็จ
)
echo.

REM ----- activate venv -----
echo [4/6] กำลัง activate venv...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] activate venv ไม่สำเร็จ
    pause
    exit /b 1
)
echo       activate สำเร็จ
echo.

REM ----- ติดตั้ง library จาก requirements.txt (ถ้ามีไฟล์นี้อยู่) -----
echo [5/6] กำลังติดตั้ง library จาก requirements.txt...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    echo       ไม่พบไฟล์ requirements.txt ข้ามขั้นตอนนี้
)
echo.

REM ----- ติดตั้ง library เพิ่มเติมที่ javis.py ต้องใช้ -----
echo [6/6] กำลังติดตั้ง library เพิ่มเติมที่จำเป็น...
pip install pyaudio edge-tts deep-translator playsound==1.2.2 pyperclip
echo.

echo ================================================
echo   ติดตั้งเสร็จสมบูรณ์!
echo   รันโปรแกรมด้วยคำสั่ง: venv\Scripts\activate  แล้วตามด้วย  python javis.py
echo ================================================
echo.
pause
