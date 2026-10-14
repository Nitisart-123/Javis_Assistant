import random
import pyttsx3
import speech_recognition as sr
import datetime
import os
import webbrowser
from urllib.parse import quote
import playsound
import asyncio
import edge_tts
from deep_translator import GoogleTranslator
import re
import subprocess
import pyperclip


# pyttsx3 เป็นไลบรารีการแปลงข้อความเป็นคำพูดใน Python
# มันทำงานแบบออฟไลน์และเข้ากันได้กับทั้ง Python 2 และ 3

# เริ่มต้นใช้งาน engine ชื่อ sapi5 (ใช้พูดภาษาอังกฤษ)
engine = pyttsx3.init('sapi5')
voices = engine.getProperty('voices')
engine.setProperty('voice', voices[0].id)


def speak(audio, lang='en'):
    """
    ฟังก์ชั่นพูด รองรับทั้งภาษาอังกฤษ (offline, เร็ว) และภาษาไทย (online, ผ่าน edge-tts)

    lang='en' -> ใช้ pyttsx3 (offline)
    lang='th' -> ใช้ edge-tts (ต้องต่อเน็ต)
    """
    if lang == 'th':
        speak_thai(audio)
    else:
        engine.say(audio)
        engine.runAndWait()


THAI_VOICE = "th-TH-NiwatNeural"  # เสียงผู้ชาย (เปลี่ยนเป็น th-TH-PremwadeeNeural ถ้าอยากได้เสียงผู้หญิง)

# โฟลเดอร์เก็บไฟล์เสียงที่เคยสร้างแล้ว เพื่อเอามาเล่นซ้ำโดยไม่ต้องต่อเน็ตสร้างใหม่
CACHE_DIR = "voice_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# ===== ระบบล้างไฟล์เสียงใน voice_cache ทุกวันอาทิตย์ =====
CACHE_CLEAR_MARKER = os.path.join(CACHE_DIR, ".last_cleared")


def clear_voice_cache_if_sunday():
    """ถ้าวันนี้เป็นวันอาทิตย์ และยังไม่เคยล้าง cache วันนี้มาก่อน ให้ลบไฟล์เสียงทั้งหมดใน voice_cache ทิ้ง"""
    today = datetime.date.today()
    if today.weekday() != 6:  # 6 = วันอาทิตย์ (จันทร์ = 0)
        return

    try:
        if os.path.exists(CACHE_CLEAR_MARKER):
            with open(CACHE_CLEAR_MARKER, 'r', encoding='utf-8') as f:
                last_cleared = f.read().strip()
            if last_cleared == str(today):
                return  # ล้างไปแล้วเมื่อวันอาทิตย์นี้ ไม่ต้องล้างซ้ำ

        for filename in os.listdir(CACHE_DIR):
            if filename == os.path.basename(CACHE_CLEAR_MARKER):
                continue
            file_path = os.path.join(CACHE_DIR, filename)
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"ลบไฟล์ cache ไม่สำเร็จ: {file_path} - {e}")

        with open(CACHE_CLEAR_MARKER, 'w', encoding='utf-8') as f:
            f.write(str(today))

        print("ล้าง voice_cache เรียบร้อยแล้ว (วันอาทิตย์)")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดตอนล้าง voice_cache: {e}")



async def _generate_thai_voice(text, filename):
    """สร้างไฟล์เสียงภาษาไทยด้วย edge-tts"""
    communicate = edge_tts.Communicate(text, THAI_VOICE)
    await communicate.save(filename)


def speak_thai(text):
    """
    พูดภาษาไทยด้วย edge-tts (เสียงผู้ชาย)

    ประโยคไหนเคยพูดมาก่อน (ข้อความเหมือนเดิมเป๊ะ) จะเล่นจากไฟล์ cache ทันที
    ไม่ต้องต่อเน็ตสร้างใหม่ ทำให้เร็วขึ้นมากในการใช้งานซ้ำๆ เช่น
    "กำลังเปิดยูทูปครับ" ที่พูดซ้ำทุกครั้งที่สั่งเปิดยูทูป
    """
    try:
        # ตั้งชื่อไฟล์ตามเนื้อหาข้อความ (hash) แทนชื่อสุ่ม เพื่อให้ข้อความเดิมใช้ไฟล์เดิมได้
        cache_key = str(abs(hash(text)))
        cached_path = os.path.join(CACHE_DIR, f"{cache_key}.mp3")

        if not os.path.exists(cached_path):
            # ยังไม่เคยพูดประโยคนี้มาก่อน -> สร้างไฟล์เสียงใหม่แล้วเก็บไว้ใน cache
            asyncio.run(_generate_thai_voice(text, cached_path))

        playsound.playsound(cached_path)
        # หมายเหตุ: ไม่ลบไฟล์ทิ้งแล้ว เพื่อเก็บไว้ใช้ซ้ำครั้งถัดไป
    except Exception as e:
        print(f"เกิดข้อผิดพลาดตอนพูดภาษาไทย: {e}")


def commands(language='th-TH', phrase_time_limit=8):
    r = sr.Recognizer()  # สร้างตัวแปร r เพื่อรับค่าจากการฟัง

    with sr.Microphone() as source:  # ใช้ไมโครโฟนเป็น source ในการรับเสียง
        r.pause_threshold = 1  # หยุดรอคำสั่ง 1 วินาที
        print("Listening...")
        r.adjust_for_ambient_noise(source, duration=1)  # ปรับระดับเสียงรบกวน 1 วินาที
        # phrase_time_limit จำกัดความยาวสูงสุดของการอัดเสียงต่อ 1 ประโยค (วินาที)
        # ป้องกันไม่ให้พูดหลายรอบต่อเนื่องกันถูกอัดรวมเป็นไฟล์เดียว
        audio = r.listen(source, phrase_time_limit=phrase_time_limit)  # รับเสียงจากไมโครโฟน

    try:
        # ใช้ภาษาตามที่กำหนด (ค่าเริ่มต้นคือภาษาไทย)
        query = r.recognize_google(audio, language=language)

        print(f"User said: {query}\n")

    except Exception as e:
        print(e)
        print("Say that again please...")
        return "None"
    return query


# ===== ระบบอ่าน/เขียนตอนที่ดูล่าสุดจากไฟล์ notepad=====
# ที่อยู่ไฟล์ notepad ที่เก็บตัวเลขตอนของซีรีส์ต่าง ๆ
KR_MYTH_TH_SUB_EP = r"C:\Storage_File\My Programming Project\Javis-Python-main\notepad\KR MYTH TH SUB EP.txt"
ULTRAMAN_TEO_EP = r"C:\Storage_File\My Programming Project\Javis-Python-main\notepad\ULTRAMAN TEO EP.txt"
IRON_HEART_EP = r"C:\Storage_File\My Programming Project\Javis-Python-main\notepad\IRON HEART EP.txt"

# รายการเพลงแบบสุ่ม (YouTube URL) สำหรับคำสั่ง "เปิดเพลงแบบสุ่ม"
RANDOM_SONGS = [    "https://youtu.be/rX7HNu5HZ-k?si=nLEueWn2JfQRtuNw",
                    "https://youtu.be/Cx397w2vSh0?si=aQ5vedNY3Es2t_9o",
                    "https://youtu.be/1K72nmZjJqU?si=2siAMPXJ214bNnSr",
                    "https://youtu.be/nf4OHIskVBM?si=oUovBIHF2TXO8v5G",
                    "https://youtu.be/zcxV6z6s35w?si=V3Lfju8JRxbTizaV",
                    "https://youtu.be/yqpev_CQBIU?si=SFoLC6uQhw_3GlCn",
                    "https://youtu.be/OZCp_Siln1A?si=Y4ZUX6gkcCc-K-kJ",
                    "https://youtu.be/wtFbaIdF5Ic?si=Oc4JyCGCS8HMGxqJ",
                    "https://youtu.be/YrjNry07UlM?si=5pZ7ochED1CdEZIA",
                    "https://youtu.be/0Ar0ws9cL10?si=d_BQXQrM5B0PZIS9",
                    # 時花火
                    "https://youtu.be/tDlLDQDqZlQ?si=TnZrTgZKMndRC0dw",
                    # GRADUATIONS （Vシネクスト『仮面ライダーガッチャード GRADUATIONS』主題歌）
                    "https://youtu.be/0Ar0ws9cL10",
                ]

# ตำแหน่งไฟล์โปรแกรม
chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
brave_path = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"


def read_ep_number(path):
    """อ่านตัวเลขตอนล่าสุดจากไฟล์ notepad ที่ path ที่ระบุ คืนค่า None ถ้าอ่านไม่สำเร็จ/ไม่เจอตัวเลข"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        match = re.search(r'\d+', content)
        if match:
            return int(match.group())
    except Exception as e:
        print(f"เกิดข้อผิดพลาดตอนอ่านไฟล์ notepad: {e}")
    return None


def write_ep_number(ep_number, path):
    """เขียนทับไฟล์ notepad ที่ path ที่ระบุด้วยตัวเลขตอนใหม่ คืนค่า True ถ้าสำเร็จ"""
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(str(ep_number))
        return True
    except Exception as e:
        print(f"เกิดข้อผิดพลาดตอนเขียนไฟล์ notepad: {e}")
        return False


# คำที่ต้องพูดนำหน้าเสมอ ถึงจะสั่งคำสั่งอื่นได้ (ไม่มีระบบเปิด/ปิดจาวิสอีกต่อไป)
TRIGGER_WORDS = ['จาวิส', 'จาร์วิส' , 'jarvis' ]

# คำที่ใช้ยกเลิกตอนกำลังรอฟังคำค้นหา
CANCEL_WORDS = ['ยกเลิก']


if __name__ == "__main__":

    print("Jarvis พร้อมใช้งานแล้ว")
    speak("สวัสดีครับ ผมคือจาวิส มีอะไรให้ผมช่วยไหมครับ", lang='th')
    clear_voice_cache_if_sunday()  # เช็คและล้าง voice_cache ถ้าวันนี้เป็นวันอาทิตย์


    while True:
        query = commands().lower()

        # ต้องพูดคำว่า 'จาวิส' (หรือคำใน TRIGGER_WORDS) ปนอยู่ในประโยคเสมอ ถึงจะทำงานต่อ
        # ถ้าไม่มีคำนี้ -> เพิกเฉยเงียบๆ ไม่มีเสียงพูดตอบใดๆ ทั้งสิ้น แล้ววนกลับไปฟังใหม่
        if not any(trigger in query for trigger in TRIGGER_WORDS):
            continue

        # ตัดคำกระตุ้น ('จาวิส'/'จาร์วิส') ออกจาก query ก่อน กันไม่ให้คำนี้ปนเข้าไปในคำค้นหาต่างๆ ด้านล่าง
        for trigger in TRIGGER_WORDS:
            query = query.replace(trigger, '').strip()

        # พูด 'จาวิส' ครั้งเดียวพอ จากนี้จะวนฟังคำสั่งต่อไปเรื่อยๆ โดยไม่ต้องพูด 'จาวิส' ซ้ำ
        # จนกว่าจะพูดคำที่ตรงกับคำสั่งใดคำสั่งหนึ่ง (จะ break ออกจากลูปนี้เอง)
        # ถ้าพูดไม่ตรงกับคำสั่งไหนเลย จะวนฟังใหม่ต่อไปเรื่อยๆ ในลูปนี้ (ไม่ต้องพูด 'จาวิส' ซ้ำ)
        while True:
            # คำสั่งที่ให้ Javis ทำงานตามคำสั่งเสียงของผู้ใช้

            if 'ตอนนี้กี่โมง' in query:
                strTime = datetime.datetime.now().strftime("%H:%M:%S")
                speak(f"ขณะนี้เวลา {strTime} นาฬิกาครับ", lang='th')
                break


            #===== คำสั่งเปิดว็บไซต์ต่าง ๆ ======
            elif 'เปิดคอร์ส' in query or 'เปิดคอร์ด' in query:
                speak("กำลังเปิด Claude AI ครับ", lang='th')
                webbrowser.open("https://claude.ai")
                break
            elif 'เปิดเฟส' in query:
                speak("กำลังเปิด Facebook ครับ", lang='th')
                webbrowser.open("facebook.com")
                break       
            elif 'เปิดเว็บบราวเซอร์' in query or 'เปิดเว็บ browser' in query:
                speak("กำลังเปิด Brave Browser ครับ", lang='th')
                subprocess.Popen([brave_path])
                break                 

 
            # ===== คำสั่งค้นหาทั่วไป ใน YouTube หรือ Google =====
            # รูปแบบคำพูด: "ค้นหา {คีย์เวิร์ด} ใน {ยูทูป|กูเกิล}"
            elif 'ค้นหา' in query:
                # ตัดคำว่า 'ค้นหา' ตัวแรกออกจากประโยค เหลือคำค้นหา + คำระบุแพลตฟอร์ม (ถ้ามี)
                remainder = query.replace('ค้นหา', '', 1).strip()
 
                # คำที่ใช้บ่งบอกว่าต้องการค้นหาในแพลตฟอร์มไหน
                YOUTUBE_HINTS = ['ในยูทูป', 'ใน youtube', 'ในyoutube', 'youtube', 'ยูทูป']
                GOOGLE_HINTS = ['ในกูเกิล', 'ในกูเกิ้ล', 'ใน google', 'ในgoogle', 'google', 'กูเกิล', 'กูเกิ้ล']
 
                platform = None
                for hint in YOUTUBE_HINTS:
                    if hint in remainder:
                        platform = 'youtube'
                        remainder = remainder.replace(hint, '').strip()
                        break
                if platform is None:
                    for hint in GOOGLE_HINTS:
                        if hint in remainder:
                            platform = 'google'
                            remainder = remainder.replace(hint, '').strip()
                            break
 
                search_term = remainder
 
                cancelled = False
 
                # ถ้ายังไม่รู้ว่าจะค้นหาแพลตฟอร์มไหน -> ถามให้ระบุก่อน
                while platform is None:
                    speak("ต้องการค้นหาในยูทูปหรือกูเกิลครับ", lang='th')
                    platform_query = commands(phrase_time_limit=3).lower().strip()
 
                    if platform_query == "none":
                        continue
 
                    if any(cancel in platform_query for cancel in CANCEL_WORDS):
                        speak("ยกเลิกการค้นหาแล้วครับ", lang='th')
                        cancelled = True
                        break
 
                    if any(hint in platform_query for hint in YOUTUBE_HINTS):
                        platform = 'youtube'
                    elif any(hint in platform_query for hint in GOOGLE_HINTS):
                        platform = 'google'
                    else:
                        speak("ไม่เข้าใจครับ กรุณาพูดว่า ยูทูป หรือ กูเกิล", lang='th')
 
                # ถ้าพูดคำค้นหามาพร้อมกับคำสั่งเลย และมีคำว่า "ภาษาอังกฤษ" ปนมาด้วย -> แปลทันทีโดยไม่ต้องรอฟังใหม่
                if not cancelled and search_term and 'ภาษาอังกฤษ' in search_term:
                    thai_text = search_term.replace('ภาษาอังกฤษ', '').strip()
                    if thai_text:
                        try:
                            search_term = GoogleTranslator(source='th', target='en').translate(thai_text).lower()
                        except Exception as e:
                            print(f"เกิดข้อผิดพลาดตอนแปลภาษา: {e}")
                            speak("แปลภาษาไม่สำเร็จครับ กรุณาบอกคำค้นหาอีกครั้ง", lang='th')
                            search_term = ""  # เคลียร์ค่าทิ้ง เพื่อให้ตกไปที่ลูปรอฟังใหม่ด้านล่าง
                    else:
                        search_term = ""  # พูดแค่ "ภาษาอังกฤษ" เฉยๆ ไม่มีคำให้แปล -> ต้องถามใหม่
 
                while not cancelled and not search_term:
                    # ไม่มีคำค้นหามาด้วย -> รอฟังคำค้นหาซ้ำไปเรื่อยๆ จนกว่าจะได้คำ หรือสั่งยกเลิก
                    speak("กรุณาบอกคำที่ต้องการค้นหาครับ", lang='th')
                    next_query = commands(phrase_time_limit=3).lower().strip()
 
                    if next_query == "none":
                        # ฟังไม่ออก/ไม่มีเสียง -> วนถามใหม่อีกรอบ
                        continue
 
                    if any(cancel in next_query for cancel in CANCEL_WORDS):
                        speak("ยกเลิกการค้นหาแล้วครับ", lang='th')
                        cancelled = True
                        break
 
                    if 'ภาษาอังกฤษ' in next_query:
                        # ผู้ใช้ระบุว่าต้องการคำค้นหาเป็นภาษาอังกฤษ -> ตัดคำว่า "ภาษาอังกฤษ" ออก
                        # แล้วแปลข้อความที่เหลือ (ภาษาไทย) เป็นภาษาอังกฤษด้วยระบบแปลภาษา (ไม่ต้องพูดซ้ำ)
                        thai_text = next_query.replace('ภาษาอังกฤษ', '').strip()
 
                        if not thai_text:
                            speak("กรุณาบอกคำที่ต้องการแปลด้วยครับ", lang='th')
                            continue
 
                        try:
                            search_term = GoogleTranslator(source='th', target='en').translate(thai_text).lower()
                        except Exception as e:
                            print(f"เกิดข้อผิดพลาดตอนแปลภาษา: {e}")
                            speak("แปลภาษาไม่สำเร็จครับ ลองพูดใหม่อีกครั้งนะครับ", lang='th')
                            continue
                    else:
                        search_term = next_query
 
                if not cancelled:
                    if platform == 'youtube':
                        speak(f"กำลังค้นหา {search_term} ในยูทูปครับ", lang='th')
                        webbrowser.open(f"https://www.youtube.com/results?search_query={quote(search_term)}")
                    elif platform == 'google':
                        speak(f"กำลังค้นหา {search_term} ในกูเกิลครับ", lang='th')
                        webbrowser.open(f"https://www.google.com/search?q={quote(search_term)}")
                break

            # ===== คำสั่งเปิดคอนเทนต์ต่าง ๆ ในยูทูป ======
            elif 'เปิดยูทูป' in query or 'เปิด youtube' in query or 'ดูยูทูป' in query or 'ดู youtube' in query:
                # ตัดคำสั่งนำหน้าออก เหลือแค่คำที่พูดต่อท้าย ไว้เช็คว่าต้องการเพลย์ลิสต์ไหนเป็นพิเศษหรือไม่
                playlist_keyword = query.replace('เปิดยูทูป', '').replace('เปิด youtube', '').replace('ดูยูทูป', '').replace('ดู youtube', '').strip()

                if 'เขียนโปรแกรม' in playlist_keyword:
                    speak("กำลังเปิดยูทูปเพลย์ลิสต์เขียนโปรแกรมครับ", lang='th')
                    subprocess.Popen([brave_path, "https://www.youtube.com/playlist?list=PL2wEVxYkxxMcFMsvTVG4IrIOWRmBJzRNa"])
                elif 'ดูภายหลัง' in playlist_keyword:
                    speak("กำลังเปิดยูทูปเพลย์ลิสต์ดูภายหลังครับ", lang='th')
                    subprocess.Popen([brave_path, "https://www.youtube.com/playlist?list=WL"])
                elif 'โหลดโปรแกรม' in playlist_keyword:
                    speak("กำลังเปิดยูทูปเพลย์ลิสต์โหลดโปรแกรมครับ", lang='th')
                    subprocess.Popen([brave_path, "https://www.youtube.com/playlist?list=PL2wEVxYkxxMeYe7wlIGh293muwQ1nDgjY"])
                elif 'การติดตาม' in playlist_keyword or 'ติดตาม' in playlist_keyword:
                    speak("กำลังเปิดยูทูปหน้าการติดตามครับ", lang='th')
                    subprocess.Popen([brave_path, "https://www.youtube.com/feed/subscriptions"])
                elif 'ช่องสำรอง' in playlist_keyword or 'สำรอง' in playlist_keyword:
                    speak("กำลังเปิดยูทูปโปรไฟล์อวตารแสงมืดหน้าดูภายหลังครับ", lang='th')
                    subprocess.Popen([chrome_path, "--profile-directory=Profile 1", "https://www.youtube.com/playlist?list=WL"])
                elif 'ดูตอนกินข้าว' in playlist_keyword:
                    speak("กำลังเปิดยูทูปเพลย์ลิสต์ดูตอนกินข้าวครับ", lang='th')
                    subprocess.Popen([brave_path, "https://www.youtube.com/playlist?list=PL2wEVxYkxxMcfJWIphv27dPxRc61EZtHS"])
                elif 'ไอดอล like' in playlist_keyword or 'idol live' in playlist_keyword or 'Idol like' in playlist_keyword:
                    speak("กำลังเปิดยูทูปเพลย์ลิสต์ Idol Live ครับ", lang='th')
                    subprocess.Popen([brave_path, "https://www.youtube.com/playlist?list=PL2wEVxYkxxMc-aSzygz7zqS4bfCULQ_a9"])
                else:
                    # ไม่มีคีย์เวิร์ดพิเศษต่อท้าย -> เปิดหน้าแรกของยูทูปตามปกติ
                    speak("กำลังเปิดยูทูปหน้าแรกครับ", lang='th')
                    subprocess.Popen([brave_path, "https://www.youtube.com"])
                break


            # ===== คำสั่งเปิดเพลง =====
            elif 'เปิดเพลงแบบสุ่ม' in query or 'สุ่มเปิดเพลง' in query:
                song_url = random.choice(RANDOM_SONGS)
                speak("กำลังสุ่มเปิดเพลงให้ครับ", lang='th')
                subprocess.Popen([brave_path, song_url])
                break

            # ===== คำสั่งเปิดเว็บไซต์จับเวลา =====
            elif 'จับเวลา' in query:
                speak("กำลังเปิดเว็บไซต์จับเวลาครับ", lang='th')
                subprocess.Popen([brave_path, "https://stopwatch.thaiware.com/"])
                break

            # ==== คำสั่งเปิดซีรีส์ Kamen Rider MY-TH ตามตอนล่าสุดที่บันทึกไว้ในไฟล์ notepad ======
            # คำสั่งอัพเดตตอนซีรีส์หลังดูจบแล้ว
            elif 'ดูไมค์จบแล้ว' in query or 'ดูไม้จบแล้ว' in query:
                krEpNow = read_ep_number(KR_MYTH_TH_SUB_EP)
                speak(f"คุณดูซีรี่ส์คาเมนไรเดอร์ไมซ์ซับไทยตอนที่ {krEpNow} จบแล้ว ต้องการอัพเดตตอนถัดไปไหมครับ", lang='th')

                updated = False
                while not updated:
                    next_query = commands(phrase_time_limit=3).lower().strip()

                    if next_query == "none":
                        # ฟังไม่ออก/ไม่มีเสียง -> วนถามใหม่อีกรอบ
                        continue

                    # เพิ่มคำสั่ง 'ไม่อัพเดต' , 'ไม่ต้อง' สำหรับไม่อัพเดตตัวเลขใน notepad krthverEpNow
                    if 'ไม่อัพเดต' in next_query or 'ไม่ต้อง' in next_query:
                        speak("ไม่มีการอัพเดตตอนครับ", lang='th')
                        updated = True

                    # เพิ่มคำสั่ง 'กำหนดเอง' สำหรับอัพเดตตัวเลขแบบกำหนดเอง krthverEpNow = EP ที่ผู้ใช้กำหนด
                    elif 'กำหนดเอง' in next_query:
                        speak("กรุณาบอกหมายเลขตอนที่ต้องการกำหนดครับ", lang='th')
                        ep_query = commands(phrase_time_limit=3).lower().strip()
                        match = re.search(r'\d+', ep_query)

                        if match:
                            krEpNow = int(match.group())
                            if write_ep_number(krEpNow, KR_MYTH_TH_SUB_EP):
                                speak(f"กำหนดตอนที่ {krEpNow} เรียบร้อยครับ", lang='th')
                            else:
                                speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                            updated = True
                        else:
                            speak("ไม่ได้ยินหมายเลขตอนที่ชัดเจนครับ ลองพูดคำสั่งใหม่อีกครั้งนะครับ", lang='th')
                            updated = True

                    # เพิ่มคำสั่ง 'อัพเดต' สำหรับอัพเดตตัวเลขใน notepad nowEP+1
                    elif 'อัพเดต' in next_query or 'อัพเดท' in next_query:
                        if krEpNow is not None:
                            krEpNow += 1
                            if write_ep_number(krEpNow, KR_MYTH_TH_SUB_EP):
                                speak(f"อัพเดตเป็นตอนที่ {krEpNow} เรียบร้อยครับ", lang='th')
                            else:
                                speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        else:
                            speak("อ่านตัวเลขเดิมจากไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        updated = True

                    else:
                        speak("ไม่เข้าใจคำสั่งครับ กรุณาพูดว่า อัพเดต หรือ ไม่อัพเดต หรือ กำหนดเอง", lang='th')
                break
            # คำสั่งเปิดซีรีส์ตามตอนที่บันทึกไว้ในไฟล์ notepad
            elif 'เปิดไมค์ซับไทย' in query or 'เปิดไม้ซับไทย' in query:
                krEpNow = read_ep_number(KR_MYTH_TH_SUB_EP)
                if krEpNow is not None:
                    speak(f"กำลังเปิดซีรีส์คาเมนไรเดอร์ไมซ์ซับไทยตอนที่ {krEpNow} ครับ", lang='th')
                    subprocess.Popen([brave_path, f"https://www.youtube.com/results?search_query=kamen rider my-th ep {krEpNow} ซับไทย"])
                else:
                    speak("อ่านตัวเลขตอนจากไฟล์ notepad ไม่สำเร็จครับ กรุณาตรวจสอบไฟล์", lang='th')
                break

            # คำสั่งดูซีรีส์ Ultraman Teo ตอนล่าสุด
            elif 'ดูเทโอจบแล้ว' in query or 'ดู ko จบแล้ว' in query or 'ดู to จบแล้ว' in query:
                ultramanTeoEpNow = read_ep_number(ULTRAMAN_TEO_EP)
                speak(f"คุณดูซีรีส์ Ultraman Teo พากย์ไทยตอนที่ {ultramanTeoEpNow} จบแล้ว ต้องการอัพเดตตอนถัดไปไหมครับ", lang='th')

                updated = False
                while not updated:
                    next_query = commands(phrase_time_limit=3).lower().strip()

                    if next_query == "none":
                        # ฟังไม่ออก/ไม่มีเสียง -> วนถามใหม่อีกรอบ
                        continue

                    # เพิ่มคำสั่ง 'ไม่อัพเดต' , 'ไม่ต้อง' สำหรับไม่อัพเดตตัวเลขใน notepad krthverEpNow
                    if 'ไม่อัพเดต' in next_query or 'ไม่ต้อง' in next_query:
                        speak("ไม่มีการอัพเดตตอนครับ", lang='th')
                        updated = True

                    # เพิ่มคำสั่ง 'กำหนดเอง' สำหรับอัพเดตตัวเลขแบบกำหนดเอง krthverEpNow = EP ที่ผู้ใช้กำหนด
                    elif 'กำหนดเอง' in next_query:
                        speak("กรุณาบอกหมายเลขตอนที่ต้องการอัพเดตครับ", lang='th')
                        ep_query = commands(phrase_time_limit=3).lower().strip()
                        match = re.search(r'\d+', ep_query)

                        if match:
                            ultramanTeoEpNow = int(match.group())
                            if write_ep_number(ultramanTeoEpNow, ULTRAMAN_TEO_EP):
                                speak(f"กำหนดตอนที่ {ultramanTeoEpNow} เรียบร้อยครับ", lang='th')
                            else:
                                speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                            updated = True
                        else:
                            speak("ไม่ได้ยินหมายเลขตอนที่ชัดเจนครับ ลองพูดคำสั่งใหม่อีกครั้งนะครับ", lang='th')
                            updated = True

                    # เพิ่มคำสั่ง 'อัพเดต' สำหรับอัพเดตตัวเลขใน notepad nowEP+1
                    elif 'อัพเดท' in next_query or 'update' in next_query:
                        if ultramanTeoEpNow is not None:
                            ultramanTeoEpNow += 1
                            if write_ep_number(ultramanTeoEpNow, ULTRAMAN_TEO_EP):
                                speak(f"อัพเดตเป็นตอนที่ {ultramanTeoEpNow} เรียบร้อยครับ", lang='th')
                            else:
                                speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        else:
                            speak("อ่านตัวเลขเดิมจากไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        updated = True

                    else:
                        speak("ไม่เข้าใจคำสั่งครับ กรุณาพูดว่า อัพเดต หรือ ไม่อัพเดต หรือ กำหนดเอง", lang='th')
                break
            elif 'เปิด ko' in query or 'เปิด to' in query or 'เปิดเทโอ' in query:
                ultramanTeoEpNow = read_ep_number(ULTRAMAN_TEO_EP)
                if ultramanTeoEpNow is not None:
                    speak(f"กำลังเปิดซีรีส์ Ultraman Teo ตอนที่ {ultramanTeoEpNow} ครับ", lang='th')
                    webbrowser.open(f"https://www.youtube.com/results?search_query=ultraman teo ep {ultramanTeoEpNow}")
                else:
                    speak("อ่านตัวเลขตอนจากไฟล์ notepad ไม่สำเร็จครับ กรุณาตรวจสอบไฟล์", lang='th')
                break  

            # ==== คำสั่งดูซีรีส์ Iron Heart ======
            elif 'ดูไอรอนฮาร์ทจบแล้ว' in query or 'ดู iron heart จบแล้ว' in query:
                ironHeartEpNow = read_ep_number(IRON_HEART_EP)
                speak(f"คุณดูซีรีส์ Iron Heart ตอนที่ {ironHeartEpNow} จบแล้ว ต้องการอัพเดตตอนถัดไปไหมครับ", lang='th')

                updated = False
                while not updated:
                    next_query = commands(phrase_time_limit=3).lower().strip()

                    if next_query == "none":
                        # ฟังไม่ออก/ไม่มีเสียง -> วนถามใหม่อีกรอบ
                        continue

                    # เพิ่มคำสั่ง 'ไม่อัพเดต' , 'ไม่ต้อง' สำหรับไม่อัพเดตตัวเลขใน notepad krthverEpNow
                    if 'ไม่อัพเดต' in next_query or 'ไม่ต้อง' in next_query:
                        speak("ไม่มีการอัพเดตตอนครับ", lang='th')
                        updated = True

                    # เพิ่มคำสั่ง 'กำหนดเอง' สำหรับอัพเดตตัวเลขแบบกำหนดเอง krthverEpNow = EP ที่ผู้ใช้กำหนด
                    elif 'กำหนดเอง' in next_query:
                        speak("กรุณาบอกหมายเลขตอนที่ต้องการอัพเดตครับ", lang='th')
                        ep_query = commands(phrase_time_limit=3).lower().strip()
                        match = re.search(r'\d+', ep_query)

                        if match:
                            ironHeartEpNow = int(match.group())
                            if write_ep_number(ironHeartEpNow, IRON_HEART_EP):
                                speak(f"กำหนดตอนที่ {ironHeartEpNow} เรียบร้อยครับ", lang='th')
                            else:
                                speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                            updated = True
                        else:
                            speak("ไม่ได้ยินหมายเลขตอนที่ชัดเจนครับ ลองพูดคำสั่งใหม่อีกครั้งนะครับ", lang='th')
                            updated = True

                    # เพิ่มคำสั่ง 'อัพเดต' สำหรับอัพเดตตัวเลขใน notepad nowEP+1
                    elif 'อัพเดท' in next_query or 'update' in next_query:
                        if ironHeartEpNow is not None:
                            ironHeartEpNow += 1
                            if write_ep_number(ironHeartEpNow, IRON_HEART_EP):
                                speak(f"อัพเดตเป็นตอนที่ {ironHeartEpNow} เรียบร้อยครับ", lang='th')
                            else:
                                speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        else:
                            speak("อ่านตัวเลขเดิมจากไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        updated = True

                    else:
                        speak("ไม่เข้าใจคำสั่งครับ กรุณาพูดว่า อัพเดต หรือ ไม่อัพเดต หรือ กำหนดเอง", lang='th')
                break
            elif 'เปิดไอรอนฮาร์ท' in query or 'เปิด iron heart' in query:
                ironHeartEpNow = read_ep_number(IRON_HEART_EP)
                if ironHeartEpNow is not None:
                    speak(f"กำลังเปิดซีรีส์ Iron Heart ตอนที่ {ironHeartEpNow} ครับ", lang='th')
                    webbrowser.open(f"https://9.9nung.com/episodes/%e0%b9%84%e0%b8%ad%e0%b8%a3%e0%b8%ad%e0%b8%99%e0%b8%ae%e0%b8%b2%e0%b8%a3%e0%b9%8c%e0%b8%95-1x{ironHeartEpNow}/")
                else:
                    speak("อ่านตัวเลขตอนจากไฟล์ notepad ไม่สำเร็จครับ กรุณาตรวจสอบไฟล์", lang='th')
                break              

            # คำสั่งเปิดเฟสบุ๊ค
            elif 'เปิดเฟสบุ๊ค' in query or 'เปิด facebook' in query:
                speak(f"กำลังเปิด Facebook ครับ", lang='th')
                webbrowser.open("https://www.facebook.com/")
                break


            #===== คำสั่งเปิดไฟล์ต่าง ๆ ในเครื่อง (เช่น เปิดโปรแกรม Notepad, เปิดโฟลเดอร์ Documents) =====
            # คำสั่งเปิดไฟล์โครงงาน
            elif 'เปิดโครงงาน' in query:
                speak("กำลังเปิดไฟล์โฟลเดอร์ที่เกี่ยวกับโครงงานครับ", lang='th')
                # เส้นทางไปยังไฟล์โครงงานที่ต้องการเปิด (แก้ path ตรงนี้ให้ตรงกับไฟล์จริงในเครื่องคุณ)
                project_file = r"C:\Storage_File\โครงงาน\รูปเล่ม\รูปเล่ม.doc"
                # เส้นทางไปยังโฟลเดอร์โครงงาน (แก้ path ตรงนี้ให้ตรงกับโฟลเดอร์จริงในเครื่องคุณ)
                project_folder = r"C:\Storage_File\โครงงาน\รูปเล่ม"
                try:
                    if os.path.exists(project_file):
                        os.startfile(project_file)
                    else:
                        print(f"ไม่พบไฟล์: {project_file}")
                        speak("ไม่พบไฟล์โครงงานครับ", lang='th')

                    if os.path.exists(project_folder):
                        os.startfile(project_folder)
                    else:
                        print(f"ไม่พบโฟลเดอร์: {project_folder}")
                        speak("ไม่พบโฟลเดอร์โครงงานครับ", lang='th')
                except Exception as e:
                    print(f"เกิดข้อผิดพลาดตอนเปิดไฟล์/โฟลเดอร์: {e}")
                    speak("เปิดไฟล์หรือโฟลเดอร์ไม่สำเร็จครับ", lang='th')
                break

            elif 'เปิดวงจรโหนดเซ็นเซอร์' in query or 'เปิดวงจรกล่องเซ็นเซอร์' in query or 'เปิดวงจร node sensor' in query:
                speak("กำลังเปิดโฟลเดอร์วงจรโหนดเซนเซอร์ครับ", lang='th')
                # เส้นทางไปยังโฟลเดอร์โครงงาน (แก้ path ตรงนี้ให้ตรงกับโฟลเดอร์จริงในเครื่องคุณ)
                project_folder = r"C:\Storage_File\โครงงาน\รูปเล่ม\รูปภาพ\วงจรกล่องเซนเซอร์"
                try:
                    if os.path.exists(project_folder):
                        os.startfile(project_folder)
                    else:
                        print(f"ไม่พบโฟลเดอร์: {project_folder}")
                        speak("ไม่พบโฟลเดอร์วงจรโหนดเซนเซอร์ครับ", lang='th')
                except Exception as e:
                    print(f"เกิดข้อผิดพลาดตอนเปิดโฟลเดอร์: {e}")
                    speak("เปิดโฟลเดอร์ไม่สำเร็จครับ", lang='th')
                break

            # เปิดเว็บไซต์และโฟลเดอร์ฝึกพิมพ์คีย์บอร์ดที่โปรไฟล์ อวตารปตรี
            elif 'เปิดคีย์บอร์ด' in query:
                speak("กำลังเปิดโฟลเดอร์และเว็บไซต์ฝึกพิมพ์คีย์บอร์ดที่โปรไฟล์ อวตารปอตรีครับ", lang='th')
                project_folder = r"C:\Storage_File\แคปหน้าจอ\ฝึกพิมคีย์บอร์ด"
                try:
                    if os.path.exists(project_folder):
                        os.startfile(project_folder)
                    else:
                        print(f"ไม่พบโฟลเดอร์: {project_folder}")
                        speak("ไม่พบโฟลเดอร์ฝึกพิมพ์คีย์บอร์ดครับ", lang='th')
                except Exception as e:
                    print(f"เกิดข้อผิดพลาดตอนเปิดโฟลเดอร์: {e}")
                    speak("เปิดโฟลเดอร์ไม่สำเร็จครับ", lang='th')
                subprocess.Popen([chrome_path, "--profile-directory=Profile 2", "https://www.typingstudy.com/th-thai_kedmanee-3/lesson/1"])
                break

             # ===== คำสั่งสร้างชื่อไฟล์จากวันที่และเวลาปัจจุบัน =====
            elif 'สร้างชื่อไฟล์' in query or 'ตั้งชื่อไฟล์' in query:
                # รูปแบบ: ปี(4หลัก)เดือน(2หลัก)วัน(2หลัก)ชั่วโมง(2หลัก)นาที(2หลัก)วินาที(2หลัก)
                # ตัวอย่าง: 20260723153045
                generated_filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                print(f"ชื่อไฟล์ที่สร้าง: {generated_filename}")

                try:
                    pyperclip.copy(generated_filename)
                    speak(f"ชื่อไฟล์ที่สร้างคือ {generated_filename} คัดลอกใส่คลิปบอร์ดให้แล้วครับ", lang='th')
                except Exception as e:
                    print(f"เกิดข้อผิดพลาดตอนคัดลอกเข้าคลิปบอร์ด: {e}")
                    speak(f"ชื่อไฟล์ที่สร้างคือ {generated_filename} ครับ แต่คัดลอกเข้าคลิปบอร์ดไม่สำเร็จครับ", lang='th')
                break

            # ยกเลิกคำสั่ง
            elif 'ยกเลิก' in query or 'ยกเลิกคำสั่ง' in query:
                speak("ยกเลิกคำสั่งเรียบร้อยครับ", lang='th')
                break


            else:
                # พูดไม่ตรงกับคำสั่งไหนเลย -> แจ้งเตือน แล้ว "ฟังใหม่โดยไม่ต้องพูด 'จาวิส' ซ้ำ" วนอยู่ในลูปนี้ต่อไป
                speak("ขอโทษครับ ผมไม่เข้าใจคำสั่งนี้ ลองพูดใหม่อีกครั้งนะครับ", lang='th')
                print(f"คำที่คุณพูด: {query}\n")
                query = commands().lower().strip()
                continue

