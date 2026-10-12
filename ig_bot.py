import os
import time
import re
import requests
from html import unescape
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.keys import Keys

--- কনফিগারেশন (আপনার Termux পথ অনুযায়ী) ---

API = "https://api.edu-mails.com/api"
SIGNUP_URL = "https://www.instagram.com/accounts/emailsignup/"

Termux-এ Chromium এবং ChromeDriver-এর লোকেশন

যদি আপনার পথ আলাদা হয়, তবে এখানে পরিবর্তন করুন

CHROMIUM = "/data/data/com.termux/files/usr/bin/chromium-browser"
CHROMEDRIVER = "/data/data/com.termux/files/usr/bin/chromedriver"

--- API ফাংশন ---

def create_email():
"""EduMails API থেকে নতুন ইমেইল তৈরি করে"""
try:
response = requests.post(
f"{API}/emails/generate",
json={"action": "random"},
headers={"Accept": "application/json"},
timeout=20
)
response.raise_for_status()
result = response.json()

if result.get("status") != "success":  
        raise RuntimeError(f"Email API Error: {result}")  

    email_data = result["data"]["email"]  
    return {  
        "address": email_data["address"],  
        "uuid": email_data["uuid"],  
        "has_password": email_data.get("has_password", False)  
    }  
except Exception as e:  
    print(f"ইমেইল তৈরিতে সমস্যা: {e}")  
    return None

def fetch_inbox_messages(inbox_info):
"""ইনবক্স থেকে মেসেজগুলো আনে"""
headers = {"Accept": "application/json"}
try:
response = requests.get(
f"{API}/emails/{inbox_info['uuid']}",
headers=headers,
timeout=20
)
response.raise_for_status()
return response.json().get("data", {}).get("messages", [])
except Exception as e:
print(f"ইনবক্স চেক করতে সমস্যা: {e}")
return []

def extract_otp_from_message(message_body):
"""ইমেইল বডি থেকে OTP কোড বের করে"""
if not message_body:
return None

# HTML ট্যাগগুলো সরিয়ে শুধু টেক্সট রাখে  
text = re.sub(r"<[^>]+>", " ", message_body)  
text = unescape(text)  
text = re.sub(r"\s+", " ", text).strip()  
  
# Regex দিয়ে ৬ ডিজিটের কোড খোঁজা  
# প্যাটার্ন ১: "Your code is 123456" এর মতো  
match = re.search(r'code\s*(?:is|:)?\s*(\d{6})', text, re.IGNORECASE)  
if match:  
    return match.group(1)  
      
# প্যাটার্ন ২: টেক্সটের মাঝে যেকোনো ৬ ডিজিটের সংখ্যা  
match = re.search(r'\b(\d{6})\b', text)  
if match:  
    return match.group(1)  

return None

--- Selenium Automation ---

def setup_driver():
"""Headless Chromium ব্রাউজার সেটআপ করে"""
if not os.path.isfile(CHROMIUM):
raise FileNotFoundError("Chromium পাওয়া যায়নি। পথ চেক করুন।")
if not os.path.isfile(CHROMEDRIVER):
raise FileNotFoundError("ChromeDriver পাওয়া যায়নি। পথ চেক করুন।")

options = Options()  
options.binary_location = CHROMIUM  
options.add_argument("--headless")  
options.add_argument("--no-sandbox")  
options.add_argument("--disable-dev-shm-usage")  
options.add_argument("--disable-gpu")  
options.add_argument("--window-size=1920,1080")

(3/5) # ইউজার এজেন্ট সেট করা যাতে মোবাইল বা ডেস্কটপ ব্লক না করে
options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(CHROMEDRIVER), options=options)  
return driver

def perform_instagram_signup(driver, email_address, full_name, password):
"""Instagram সাইনআপ ফর্ম ফিল করে সাবমিট করে"""
try:
driver.get(SIGNUP_URL)
# ইমেইল ইনপুট বক্স আসা পর্যন্ত অপেক্ষা
WebDriverWait(driver, 15).until(
EC.presence_of_element_located((By.NAME, "email"))
)

# ইমেইল ফিল করা  
    email_input = driver.find_element(By.NAME, "email")  
    email_input.clear()  
    email_input.send_keys(email_address)  
      
    # নামের ফিল্ড (কিছু পেজে নাম আগে চাই, কিছু পেজে পরে)  
    try:  
        # যদি আলাদা First/Last Name ফিল্ড থাকে  
        first_name = driver.find_element(By.NAME, "firstName")  
        last_name = driver.find_element(By.NAME, "lastName")  
        name_parts = full_name.split()  
        first_name.send_keys(name_parts[0])  
        if len(name_parts) > 1:  
            last_name.send_keys(name_parts[1])  
    except NoSuchElementException:  
        # যদি একসাথে Full Name ফিল্ড থাকে  
        try:  
            full_name_input = driver.find_element(By.NAME, "fullName")  
            full_name_input.send_keys(full_name)  
        except:  
            pass # যদি নামের ফিল্ড নাও থাকে, টেনশন নেই  

    # পাসওয়ার্ড ফিল করা  
    password_input = driver.find_element(By.NAME, "pass")  
    password_input.send_keys(password)  
      
    # সাবমিট বাটন খোঁজা  
    try:  
        submit_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'sqdOP') and contains(@class, 'L3NKy')]")  
        submit_btn.click()  
    except:  
        # ব্যাকআপ প্ল্যান: সাধারণ সাবমিট বাটন  
        driver.find_element(By.XPATH, "//button[@type='submit']").click()  
          
    print("ফর্ম সাবমিট করা হয়েছে। OTP পেজের জন্য অপেক্ষা করছি...")  
    return True  

except Exception as e:  
    print(f"সাইনআপ অটোমেশন এরর: {e}")  
    return False

def handle_otp_verification(driver, inbox_info, timeout_seconds=90):
"""ইমেইলে আসা OTP খুঁজে বের করে এবং ব্রাউজারে ইনপুট করে"""
start_time = time.time()

while time.time() - start_time < timeout_seconds:  
    messages = fetch_inbox_messages(inbox_info)  
      
    if messages:  
        # সর্বশেষ মেসেজটি নেওয়া  
        latest_msg = messages[-1]  
        body = latest_msg.get("body", "")  
          
        otp_code = extract_otp_from_message(body)  
          
        if otp_code:  
            print(f"OTP পাওয়া গেছে: {otp_code}")  
            return enter_otp_in_browser(driver, otp_code)  
      
    # ৫ সেকেন্ড পরপর চেক করা  
    time.sleep(5)  
  
print("OTP পেতে টাইম আউট হয়েছে।")  
return False

(4/5) def enter_otp_in_browser(driver, otp_code):
"""ব্রাউজারে OTP ইনপুট করে সাবমিট করে"""
try:
# OTP ইনপুট বক্স আসা পর্যন্ত অপেক্ষা
# নোট: Instagram-এর ক্লাস নেম বারবার বদলায়, এটি সর্বশেষ জ্ঞাত ক্লাস
WebDriverWait(driver, 10).until(
EC.presence_of_element_located((By.CLASS_NAME, "i0vgv6"))
)

otp_inputs = driver.find_elements(By.CLASS_NAME, "i0vgv6")  
      
    if len(otp_inputs) == 1:  
        # যদি একটা বক্সে পুরো কোড দিতে হয়  
        otp_inputs[0].clear()  
        otp_inputs[0].send_keys(otp_code)  
    elif len(otp_inputs) == len(otp_code):  
        # যদি প্রতিটি ডিজিটের জন্য আলাদা বক্স থাকে  
        for i, char in enumerate(otp_code):  
            otp_inputs[i].send_keys(char)  
    else:  
        # ব্যাকআপ: বডি ট্যাগে সরাসরি টাইপ করা  
        driver.find_element(By.TAG_NAME, "body").send_keys(otp_code)  
      
    # সাবমিট বাটন চাপা  
    time.sleep(2)  
    try:  
        verify_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'sqdOP') and contains(@class, 'L3NKy')]")  
        verify_btn.click()  
        print("OTP সাবমিট করা হয়েছে।")  
        return True  
    except NoSuchElementException:  
        # Enter চাপ দিয়ে সাবমিট করার চেষ্টা  
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.RETURN)  
        print("Enter কী দিয়ে OTP সাবমিট করা হয়েছে।")  
        return True  

except Exception as e:  
    print(f"OTP ইনপুট করতে সমস্যা: {e}")  
    return False

--- মূল বট লজিক ---

def run_bot():
print("===== Instagram Auto Signup Bot =====")
print("বটটি নিজে থেকেই:")
print("1. টেম্প ইমেইল তৈরি করবে।")
print("2. Instagram সাইনআপ করবে।")
print("3. OTP চেক করে ইনপুট করবে।")
print("-" * 30)

# ইউজার থেকে তথ্য নেওয়া  
try:  
    full_name = input("অ্যাকাউন্টের জন্য পুরো নাম দিন: ").strip()  
    password = input("অ্যাকাউন্টের পাসওয়ার্ড দিন: ").strip()  
      
    if not full_name or not password:  
        print("নাম এবং পাসওয়ার্ড খালি রাখা যাবে না।")  
        return  
except Exception:  
    return  

# ধাপ ১: ইমেইল তৈরি  
print("\n[১/৫] টেম্পোরারি ইমেইল তৈরি করা হচ্ছে...")  
inbox_info = create_email()  
if not inbox_info:  
    print("ইমেইল তৈরি ব্যর্থ।")  
    return  
print(f"ইমেইল: {inbox_info['address']}")  

# ধাপ ২: ব্রাউজার সেটআপ  
print("\n[২/৫] ব্রাউজার চালু করা হচ্ছে...")  
driver = None  
try:  
    driver = setup_driver()  
      
    # ধাপ ৩: সাইনআপ ফর্ম ফিল করা  
    print("\n[৩/৫] Instagram সাইনআপ ফর্ম পূরণ করা হচ্ছে...")  
    success = perform_instagram_signup(driver, inbox_info['address'], full_name, password)  
      
    if not success:  
        print("সাইনআপ ফর্ম সাবমিট করা যায়নি।")  
        return  

    # ধাপ ৪: OTP হ্যান্ডল করা  
    print("\n[৪/৫] ইমেইলে OTP আসার অপেক্ষা করা হচ্ছে... (সর্বোচ্চ ৯০ সেকেন্ড)")  
    otp_success = handle_otp_verification(driver, inbox_info, timeout_seconds=90)  
      
    if otp_success:  
        print("\n[৫/৫] ভেরিফিকেশন সম্পন্ন!")  
        print("অ্যাকাউন্ট তৈরি হয়েছে।")  
        print(f"ইমেইল: {inbox_info['address']}")  
        print(f"পাসওয়ার্ড: {password}")  
          
        # রেজাল্ট দেখার জন্য ব্রাউজার খোলা রাখা  
        input("\nব্রাউজার বন্ধ করতে Enter চাপুন...")  
    else:  
        print("OTP ভেরিফিকেশন ব্যর্থ বা টাইম আউট হয়েছে।")  

except Exception as e:  
    print(f"ক্রিটিক্যাল এরর: {e}")  
finally:  
    if driver:  
        driver.quit()

5/5) if name == "main":
run_bot()</pre>

