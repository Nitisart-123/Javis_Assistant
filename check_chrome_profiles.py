import json
import os

# แก้ path ตรงนี้ให้ตรงกับ Local State ในเครื่องคุณ
# ปกติจะอยู่ที่ C:\Users\<ชื่อ user Windows>\AppData\Local\Google\Chrome\User Data\Local State
LOCAL_STATE_PATH = os.path.expandvars(
    r"%LOCALAPPDATA%\Google\Chrome\User Data\Local State"
)

def list_chrome_profiles():
    try:
        with open(LOCAL_STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"เปิดไฟล์ Local State ไม่ได้: {e}")
        return

    profiles = data.get("profile", {}).get("info_cache", {})

    if not profiles:
        print("ไม่พบข้อมูลโปรไฟล์")
        return

    print(f"{'ชื่อโฟลเดอร์จริง (ใช้ใน --profile-directory)':45} | ชื่อที่แสดงใน Chrome")
    print("-" * 90)
    for folder_name, info in profiles.items():
        display_name = info.get("name", "(ไม่พบชื่อ)")
        print(f"{folder_name:45} | {display_name}")


if __name__ == "__main__":
    list_chrome_profiles()
