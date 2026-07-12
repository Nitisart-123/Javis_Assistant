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


def commands(language='th-TH'):
    r = sr.Recognizer()  # สร้างตัวแปร r เพื่อรับค่าจากการฟัง

    with sr.Microphone() as source:  # ใช้ไมโครโฟนเป็น source ในการรับเสียง
        print("Listening...")
        r.pause_threshold = 1  # หยุดรอคำสั่ง 1 วินาที
        r.adjust_for_ambient_noise(source, duration=1)  # ปรับระดับเสียงรบกวน 1 วินาที
        # phrase_time_limit จำกัดความยาวสูงสุดของการอัดเสียงต่อ 1 ประโยค (วินาที)
        # ป้องกันไม่ให้พูดหลายรอบต่อเนื่องกันถูกอัดรวมเป็นไฟล์เดียว
        audio = r.listen(source, phrase_time_limit=6)  # รับเสียงจากไมโครโฟน

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
# ที่อยู่ไฟล์ notepad ที่เก็บตัวเลขตอนของ Kamen Rider Zeztz พากย์ไทย และต้นฉบับญี่ปุ่น
KR_ZEZTZ_TH_EP = r"C:\Storage_File\My Programming Project\Javis-Python-main\notepad\KR Zeztz TH ver EP.txt"
KR_ZEZTZ_JP_EP = r"C:\Storage_File\My Programming Project\Javis-Python-main\notepad\KR Zeztz JP ver EP.txt"


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
TRIGGER_WORDS = ['จาวิส', 'จาร์วิส']

# คำที่ใช้ยกเลิกตอนกำลังรอฟังคำค้นหา
CANCEL_WORDS = ['ยกเลิก', 'ออกจาก youtube', 'ออกจากยูทูป']


if __name__ == "__main__":

    print("Jarvis พร้อมใช้งานแล้ว (ต้องพูดคำว่า 'จาวิส' นำหน้าทุกครั้งก่อนสั่งคำสั่งอื่น)")
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

        # คำสั่งที่ให้ Javis ทำงานตามคำสั่งเสียงของผู้ใช้
        if 'ตอนนี้กี่โมง' in query:
            strTime = datetime.datetime.now().strftime("%H:%M:%S")
            speak(f"ขณะนี้เวลา {strTime} นาฬิกาครับ", lang='th')


        #===== คำสั่งเปิดว็บไซต์ต่าง ๆ ======
        elif 'เปิดคอร์ส' in query or 'เปิดคอร์ด' in query:
            speak("กำลังเปิดคลอดครับ", lang='th')
            webbrowser.open("https://claude.ai")

        # คำสั่งค้นหาในยูทูป  
        elif 'ค้นหายูทูป' in query or 'ค้นหา youtube' in query:
            # ตัดคำสั่งนำหน้าออก เหลือแค่คำที่ต้องการค้นหา
            search_term = query.replace('ค้นหายูทูป', '').replace('ค้นหา youtube', '').strip()

            # ถ้าพูดคำค้นหามาพร้อมกับคำสั่งเลย และมีคำว่า "ภาษาอังกฤษ" ปนมาด้วย -> แปลทันทีโดยไม่ต้องรอฟังใหม่
            if search_term and 'ภาษาอังกฤษ' in search_term:
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

            cancelled = False
            while not search_term:
                # ไม่มีคำค้นหามาด้วย -> รอฟังคำค้นหาซ้ำไปเรื่อยๆ จนกว่าจะได้คำ หรือสั่งยกเลิก
                speak("กรุณาบอกคำที่ต้องการค้นหาครับ", lang='th')
                next_query = commands().lower().strip()

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
                speak(f"กำลังค้นหา {search_term} ในยูทูปครับ", lang='th')
                webbrowser.open(f"https://www.youtube.com/results?search_query={quote(search_term)}")


        # ===== คำสั่งเปิดคอนเทนต์ต่าง ๆ ในยูทูป ======
        elif 'เปิดยูทูป' in query or 'เปิด youtube' in query or 'ดูยูทูป' in query or 'ดู youtube' in query:
            # ตัดคำสั่งนำหน้าออก เหลือแค่คำที่พูดต่อท้าย ไว้เช็คว่าต้องการเพลย์ลิสต์ไหนเป็นพิเศษหรือไม่
            playlist_keyword = query.replace('เปิดยูทูป', '').replace('เปิด youtube', '').replace('ดูยูทูป', '').replace('ดู youtube', '').strip()
 
            if 'เขียนโปรแกรม' in playlist_keyword:
                speak("กำลังเปิดยูทูปเพลย์ลิสต์เขียนโปรแกรมครับ", lang='th')
                webbrowser.open("https://www.youtube.com/playlist?list=PL2wEVxYkxxMcFMsvTVG4IrIOWRmBJzRNa")
            elif 'ดูภายหลัง' in playlist_keyword:
                speak("กำลังเปิดยูทูปเพลย์ลิสต์ดูภายหลังครับ", lang='th')
                webbrowser.open("https://www.youtube.com/playlist?list=WL")
            elif 'โหลดโปรแกรม' in playlist_keyword:
                speak("กำลังเปิดยูทูปเพลย์ลิสต์โหลดโปรแกรมครับ", lang='th')
                webbrowser.open("https://www.youtube.com/playlist?list=PL2wEVxYkxxMeYe7wlIGh293muwQ1nDgjY")
            elif 'การติดตาม' in playlist_keyword or 'ติดตาม' in playlist_keyword:
                speak("กำลังเปิดยูทูปหน้าการติดตามครับ", lang='th')
                webbrowser.open("https://www.youtube.com/playlist?list=PL2wEVxYkxxMeYe7wlIGh293muwQ1nDgjY")
            elif 'ช่องสำรอง' in playlist_keyword or 'สำรอง' in playlist_keyword:
                speak("กำลังเปิดยูทูปโปรไฟล์อวตารแสงมืดหน้าดูภายหลังครับ", lang='th')
                chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                subprocess.Popen([chrome_path, "--profile-directory=Profile 3", "https://www.youtube.com/playlist?list=WL"])
            elif 'ดูตอนกินข้าว' in playlist_keyword:
                speak("กำลังเปิดยูทูปเพลย์ลิสต์ดูตอนกินข้าวครับ", lang='th')
                webbrowser.open("https://www.youtube.com/playlist?list=PL2wEVxYkxxMcfJWIphv27dPxRc61EZtHS")
            elif 'ไอดอลไลค์' in playlist_keyword or 'idol live' in playlist_keyword or 'Idol like' in playlist_keyword:
                speak("กำลังเปิดยูทูปเพลย์ลิสต์ Idol Live ครับ", lang='th')
                webbrowser.open("https://www.youtube.com/playlist?list=PL2wEVxYkxxMc-aSzygz7zqS4bfCULQ_a9")
 
            else:
                # ไม่มีคีย์เวิร์ดพิเศษต่อท้าย -> เปิดหน้าแรกของยูทูปตามปกติ
                speak("กำลังเปิดยูทูปหน้าแรกครับ", lang='th')
                webbrowser.open("https://www.youtube.com")
        

        # คำสั่งเปิดซีรีส์ตามตอนที่บันทึกไว้ในไฟล์ notepad
        elif 'เปิดเซ็ตพากย์ไทย' in query or 'เปิด set พากย์ไทย' in query:
            krthverEpNow = read_ep_number(KR_ZEZTZ_TH_EP)
            if krthverEpNow is not None:
                speak(f"กำลังเปิดซีรีส์ Kamen Rider Zeztz พากย์ไทยตอนที่ {krthverEpNow} ครับ", lang='th')
                webbrowser.open(f"https://www.youtube.com/results?search_query=kamen rider zeztz {krthverEpNow}")
            else:
                speak("อ่านตัวเลขตอนจากไฟล์ notepad ไม่สำเร็จครับ กรุณาตรวจสอบไฟล์", lang='th')

        # คำสั่งอัพเดตตอนซีรีส์หลังดูจบแล้ว
        elif 'ดูเซ็ตพากย์ไทยจบแล้ว' in query or 'ดู set พากย์ไทยจบแล้ว' in query:
            krthverEpNow = read_ep_number(KR_ZEZTZ_TH_EP)
            speak("ต้องการอัพเดตตอนถัดไปไหมครับ พูดว่า อัพเดต หรือ ไม่อัพเดต หรือ กำหนดเอง", lang='th')

            updated = False
            while not updated:
                next_query = commands().lower().strip()

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
                    ep_query = commands().lower().strip()
                    match = re.search(r'\d+', ep_query)

                    if match:
                        krthverEpNow = int(match.group())
                        if write_ep_number(krthverEpNow, KR_ZEZTZ_TH_EP):
                            speak(f"กำหนดตอนที่ {krthverEpNow} เรียบร้อยครับ", lang='th')
                        else:
                            speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        updated = True
                    else:
                        speak("ไม่ได้ยินหมายเลขตอนที่ชัดเจนครับ ลองพูดคำสั่งใหม่อีกครั้งนะครับ", lang='th')
                        updated = True

                # เพิ่มคำสั่ง 'อัพเดต' สำหรับอัพเดตตัวเลขใน notepad nowEP+1
                elif 'อัพเดต' in next_query:
                    if krthverEpNow is not None:
                        krthverEpNow += 1
                        if write_ep_number(krthverEpNow, KR_ZEZTZ_TH_EP):
                            speak(f"อัพเดตเป็นตอนที่ {krthverEpNow} เรียบร้อยครับ", lang='th')
                        else:
                            speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                    else:
                        speak("อ่านตัวเลขเดิมจากไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                    updated = True

                else:
                    speak("ไม่เข้าใจคำสั่งครับ กรุณาพูดว่า อัพเดต หรือ ไม่อัพเดต หรือ กำหนดเอง", lang='th')
        # คำสั่งดูซีรีส์ Kamen Rider Zeztz ตอนล่าสุด
        elif 'ดูเซ็ตจบแล้ว' in query or 'ดู set จบแล้ว' in query or 'ดูเซฟจบแล้ว' in query:
            krEpNow = read_ep_number(KR_ZEZTZ_JP_EP)
            speak(f"คุณดูซีรีส์ Kamen Rider Zeztz ตอนที่ {krEpNow} จบแล้ว ต้องการอัพเดตตอนถัดไปไหมครับ", lang='th')

            updated = False
            while not updated:
                next_query = commands().lower().strip()

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
                    ep_query = commands().lower().strip()
                    match = re.search(r'\d+', ep_query)

                    if match:
                        krEpNow = int(match.group())
                        if write_ep_number(krEpNow, KR_ZEZTZ_JP_EP):
                            speak(f"กำหนดตอนที่ {krEpNow} เรียบร้อยครับ", lang='th')
                        else:
                            speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                        updated = True
                    else:
                        speak("ไม่ได้ยินหมายเลขตอนที่ชัดเจนครับ ลองพูดคำสั่งใหม่อีกครั้งนะครับ", lang='th')
                        updated = True

                # เพิ่มคำสั่ง 'อัพเดต' สำหรับอัพเดตตัวเลขใน notepad nowEP+1
                elif 'อัพเดท' in next_query or 'update' in next_query:
                    if krEpNow is not None:
                        krEpNow += 1
                        if write_ep_number(krEpNow, KR_ZEZTZ_JP_EP):
                            speak(f"อัพเดตเป็นตอนที่ {krEpNow} เรียบร้อยครับ", lang='th')
                        else:
                            speak("บันทึกไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                    else:
                        speak("อ่านตัวเลขเดิมจากไฟล์ notepad ไม่สำเร็จครับ", lang='th')
                    updated = True

                else:
                    speak("ไม่เข้าใจคำสั่งครับ กรุณาพูดว่า อัพเดต หรือ ไม่อัพเดต หรือ กำหนดเอง", lang='th')
        elif 'ดูเซฟ' in query or 'ดู set' in query or 'เปิด set' in query or 'เปิดเซฟ' in query:
            krEpNow = read_ep_number(KR_ZEZTZ_JP_EP)
            if krEpNow is not None:
                speak(f"กำลังเปิดซีรีส์ Kamen Rider Zeztz ตอนที่ {krEpNow} ครับ", lang='th')
                webbrowser.open(f"https://kajzu.com/kamen-rider-zeztz.html?ep={krEpNow}#watch")
            else:
                speak("อ่านตัวเลขตอนจากไฟล์ notepad ไม่สำเร็จครับ กรุณาตรวจสอบไฟล์", lang='th')


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

        # เปิดเว็บไซต์และโฟลเดอร์ฝึกพิมพ์คีย์บอร์ดที่โปรไฟล์ อวตารปตรี
        elif 'เปิดคีย์บอร์ด' in query:
            speak("กำลังเปิดโฟลเดอร์และเว็บไซต์ฝึกพิมพ์คีย์บอร์ดที่โปรไฟล์ อวตารป.ตรีครับ", lang='th')
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
            chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
            subprocess.Popen([chrome_path, "--profile-directory=Profile 4", "https://www.typingstudy.com/th-thai_kedmanee-3/lesson/1"])

        else:
            speak("ขอโทษครับ ผมไม่เข้าใจคำสั่งนี้ ลองพูดใหม่อีกครั้งนะครับ", lang='th')
            print(f"คำที่คุณพูด: {query}\n")
