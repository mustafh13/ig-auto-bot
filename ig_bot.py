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
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException

# --- কনফিগারেশন ---
API = "https://api.edu-mails.com/api"
SIGNUP_URL = "https://www.instagram.com/accounts/emailsignup/"

# Termux পথ (আপনার সিস্টেম অনুযায়ী পরিবর্তন করুন)
CHROMIUM = "/data/data/com.termux/files/usr/bin/chromium-browser"
CHROMEDRIVER = "/data/data/com.termux/files/usr/bin/chromedriver"

def create_email():
    """ইমেইল জেনারেট করে"""
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
            raise RuntimeError(f"API Error: {result}")

        email_data = result["data"]["email"]
        return {
            "address": email_data["address"],
            "uuid": email_data["uuid"]
        }
    except Exception as e:
        print(f"ইমেইল জেনারেট করতে সমস্যা: {e}")
        return None

def fetch_inbox_messages(inbox_info):
    """ইনবক্স চেক করে"""
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
    """মেসেজ থেকে OTP বের করে"""
    if not message_body:
        return None
    
    # HTML ট্যাগ রিমুভ
    text = re.sub(r"<[^>]+>", " ", message_body)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()

    # ৬ ডিজিটের OTP খোঁজা (সবচেয়ে নির্ভরযোগ্য প্যাটার্ন)
    match = re.search(r'\b(\d{6})\b', text)
    if match:
        return match.group(1)
    
    # যদি ৬ ডিজিট না পাওয়া যায়, তবে ৪ বা ৫ ডিজিটও চেক করা যেতে পারে (ইনস্টাগ্রাম কখনো কখনো ৪ ডিজিট দেয়)
    match = re.search(r'\b(\d{4})\b', text)
    if match:
        return match.group(1)

    return None

def setup_driver():
    """ব্রাউজার সেটআপ"""
    options = Options()
    options.binary_location = CHROMIUM
    
    # টার্মুক্ষের জন্য জরুরি ফ্ল্যাগ
    options.add_argument("--headless=new") # নতুন হেডলেস মোড
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # ইউজার এজেন্ট
    options.add_argument("user-agent=Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    try:
        driver = webdriver.Chrome(service=Service(CHROMEDRIVER), options=options)
        return driver
    except Exception as e:
        print(f"ব্রাউজার চালু করতে সমস্যা: {e}")
        return None

def perform_instagram_signup(driver, email_address, full_name, password):
    """সাইনআপ ফর্ম পূরণ"""
    try:
        driver.get(SIGNUP_URL)
        
        # পেজ লোড হওয়ার জন্য অপেক্ষা
        time.sleep(3)

        # ১. নাম ইনপুট (Name Field)
        # ইনস্টাগ্রামে নামের ফিল্ড সাধারণত 'name' নাম অ্যাট্রিবিউটযুক্ত হয় বা class='...input'
        try:
            name_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "name")) # অনেক সময় 'name' ব্যবহার করে একাধিক ফিল্ডের জন্য
            )
            # যদি 'name' না পাওয়া যায়, তাহলে 'fullName' চেষ্টা করি
        except NoSuchElementException:
             name_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "fullName"))
            )
        
        name_input.clear()
        name_input.send_keys(full_name)
        time.sleep(1)

        # ২. ইমেইল ইনপুট
        email_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "email"))
        )
        email_input.clear()
        email_input.send_keys(email_address)
        time.sleep(1)

        # ৩. পাসওয়ার্ড ইনপুট
        password_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "password"))
        )
        password_input.clear()
        password_input.send_keys(password)
        time.sleep(1)

        # ৪. সাবমিট বাটন ক্লিক
        # সাবমিট বাটনের ক্লাস পরিবর্তনশীল, তাই XPath দিয়ে 'type="submit"' বা class চেক করা নিরাপদ
        submit_btn = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'sqdOP') and contains(@class, 'L3NKy')]"))
        )
        submit_btn.click()
        
        print("সাইনআপ বাটনে ক্লিক করা হয়েছে। OTP আসার অপেক্ষায়...")
        return True

    except TimeoutException:
        print("ফর্ম লোড হতে সময় নিয়েছে। পেজের স্ক্রিনশট নিন এবং ম্যানুয়ালি চেক করুন।")
        driver.save_screenshot("signup_error.png")
        return False
    except Exception as e:
        print(f"সাইনআপ এরর: {e}")
        return False

def handle_otp_verification(driver, inbox_info, timeout_seconds=120):
    """OTP ভেরিফিকেশন"""
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        messages = fetch_inbox_messages(inbox_info)

        if messages:
            latest_msg = messages[-1]
            body = latest_msg.get("body", "")
            
            # মেসেজটি পড়া হয়েছে কিনা চেক করা (যদি আগে পড়ে থাকে, এড়িয়ে যাবে)
            if not latest_msg.get("read"):
                otp_code = extract_otp_from_message(body)

                if otp_code:
                    print(f"OTP পাওয়া গেছে: {otp_code}")
                    return enter_otp_in_browser(driver, otp_code)

        time.sleep(5) # প্রতি ৫ সেকেন্ডে চেক করবে

    print("OTP পেতে সময় শেষ।")
    return False

def enter_otp_in_browser(driver, otp_code):
    """ব্রাউজারে OTP ইনপুট"""
    try:
        # OTP ফিল্ড খোঁজা
        # ইনস্টাগ্রামে OTP ফিল্ড সাধারণত class='i0vgv6' বা input type='tel' হতে পারে
        otp_inputs = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@type='tel']"))
        )

        if not otp_inputs:
            # যদি input[type='tel'] না পাওয়া যায়, তাহলে ক্লাস নেম দিয়ে চেষ্টা করি
            otp_inputs = driver.find_elements(By.CLASS_NAME, "i0vgv6")

        if len(otp_inputs) == 1:
            # একটি মাত্র বক্স
            otp_inputs[0].clear()
            otp_inputs[0].send_keys(otp_code)
        elif len(otp_inputs) == len(otp_code):
            # আলাদা আলাদা বক্স (যেমন: _ _ _ _)
            for i, char in enumerate(otp_code):
                if i < len(otp_inputs):
                    otp_inputs[i].send_keys(char)
        else:
            # ব্যাকআপ পদ্ধতি: বডি ট্যাগে ফোকাস করে টাইপ করা
            driver.find_element(By.TAG_NAME, "body").click()
            driver.find_element(By.TAG_NAME, "body").send_keys(otp_code)

        time.sleep(2)

        # সাবমিট বাটন ক্লিক
        # OTP সাবমিট বাটন সাধারণত 'Next' বা 'Done' লেখা থাকে
        verify_btn = driver.find_element(By.XPATH, "//button[contains(@class, 'sqdOP') and contains(@class, 'L3NKy')]")
        verify_btn.click()
        
        print("OTP সাবমিট করা হয়েছে।")
        return True

    except Exception as e:
        print(f"OTP ইনপুট করতে সমস্যা: {e}")
        # ডিবাগিংয়ের জন্য স্ক্রিনশট
        driver.save_screenshot("otp_error.png")
        return False

def run_bot():
    print("===== Instagram Auto Signup Bot (Enhanced) =====")
    
    try:
        full_name = input("নাম দিন: ").strip()
        password = input("পাসওয়ার্ড দিন: ").strip()
        
        if not full_name or not password:
            print("নাম এবং পাসওয়ার্ড প্রয়োজন।")
            return

        # ১. ইমেইল তৈরি
        print("\n[১] ইমেইল জেনারেট করা হচ্ছে...")
        inbox_info = create_email()
        if not inbox_info:
            print("ইমেইল তৈরি ব্যর্থ।")
            return
        print(f"ইমেইল: {inbox_info['address']}")

        # ২. ব্রাউজার চালু
        print("[২] ব্রাউজার চালু করা হচ্ছে...")
        driver = setup_driver()
        if not driver:
            return

        try:
            # ৩. সাইনআপ
            print("[৩] সাইনআপ ফর্ম পূরণ...")
            success = perform_instagram_signup(driver, inbox_info['address'], full_name, password)
            
            if not success:
                input("\nসাইনআপ ব্যর্থ। ব্রাউজার খোলা থাকবে। Enter চাপুন বন্ধ করতে।")
                return

            # ৪. OTP ভেরিফিকেশন
            print("[৪] OTP ভেরিফিকেশন শুরু (১২০ সেকেন্ড)...")
            otp_success = handle_otp_verification(driver, inbox_info, timeout_seconds=120)

            if otp_success:
                print("\n===== সাফল্য! অ্যাকাউন্ট তৈরি হয়েছে =====")
                print(f"ইমেইল: {inbox_info['address']}")
                print(f"পাসওয়ার্ড: {password}")
                input("\nব্রাউজার বন্ধ করতে Enter চাপুন...")
            else:
                print("\nOTP ভেরিফিকেশন ব্যর্থ।")

        finally:
            driver.quit()

    except Exception as e:
        print(f"ক্রিটিক্যাল এরর: {e}")

if __name__ == "__main__":
    run_bot()
