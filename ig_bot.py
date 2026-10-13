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

# ---------- কনফিগারেশন ----------
API = "https://api.edu-mails.com/api"
SIGNUP_URL = "https://www.instagram.com/accounts/emailsignup/"

# Termux পথ
CHROMIUM = "/data/data/com.termux/files/usr/bin/chromium-browser"
CHROMEDRIVER = "/data/data/com.termux/files/usr/bin/chromedriver"

def create_email():
    """ইমেইল জেনারেট করে"""
    try:
        r = requests.post(f"{API}/emails/generate",
                          json={"action": "random"},
                          headers={"Accept": "application/json"},
                          timeout=20)
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            raise RuntimeError(data)
        email = data["data"]["email"]
        return {"address": email["address"], "uuid": email["uuid"]}
    except Exception as e:
        print(f"ইমেইল জেনারেট করতে ব্যর্থ: {e}")
        return None

def fetch_inbox_messages(inbox_info):
    """ইনবক্স থেকে মেসেজ আনা"""
    try:
        r = requests.get(f"{API}/emails/{inbox_info['uuid']}",
                         headers={"Accept": "application/json"},
                         timeout=20)
        r.raise_for_status()
        return r.json().get("data", {}).get("messages", [])
    except Exception as e:
        print(f"ইনবক্স চেক করতে ব্যর্থ: {e}")
        return []

def extract_otp_from_message(msg):
    """মেসেজ থেকে OTP বের করা"""
    if not msg:
        return None
    text = re.sub(r"<[^>]+>", " ", msg)
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    m = re.search(r'\b(\d{6})\b', text)
    if m: return m.group(1)
    m = re.search(r'\b(\d{4})\b', text)
    if m: return m.group(1)
    return None

def setup_driver():
    """হেডলেস ক্রোম ড্রাইভার"""
    opts = Options()
    opts.binary_location = CHROMIUM
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--user-agent=Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")
    try:
        return webdriver.Chrome(service=Service(CHROMEDRIVER), options=opts)
    except Exception as e:
        print(f"ব্রাউজার চালু করতে ব্যর্থ: {e}")
        return None

def perform_instagram_signup(driver, email, fullname, pwd):
    """ফর্ম পূরণ ও সাবমিট"""
    try:
        driver.get(SIGNUP_URL)
        # পেজ লোড হওয়া পর্যন্ত অপেক্ষা
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//input[@name='fullName']"))
        )

        # ১. নাম
        name_input = driver.find_element(By.XPATH, "//input[@name='fullName']")
        name_input.clear()
        name_input.send_keys(fullname)
        time.sleep(1)

        # ২. ইমেইল
        email_input = driver.find_element(By.XPATH, "//input[@name='email']")
        email_input.clear()
        email_input.send_keys(email)
        time.sleep(1)

        # ৩. পাসওয়ার্ড
        pw_input = driver.find_element(By.XPATH, "//input[@name='password']")
        pw_input.clear()
        pw_input.send_keys(pwd)
        time.sleep(1)

        # ৪. সাবমিট
        submit_btn = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        submit_btn.click()
        print("সাবমিট বাটন ক্লিক হয়েছে, OTP‑এর জন্য অপেক্ষা করছি…")
        return True
    except TimeoutException:
        print("ফর্ম লোড হতে সময় নিয়েছে। স্ক্রিনশট: signup_error.png")
        driver.save_screenshot("signup_error.png")
        return False
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", submit_btn)
        return True
    except Exception as e:
        print(f"সাইন‑আপ এরর: {e}")
        driver.save_screenshot("signup_error.png")
        return False

def handle_otp_verification(driver, inbox_info, timeout=120):
    """OTP চেক ও ইনপুট"""
    start = time.time()
    while time.time() - start < timeout:
        msgs = fetch_inbox_messages(inbox_info)
        for m in msgs:
            if m.get("read"):  # আগেই পড়া হয়েছে কি না
                continue
            otp = extract_otp_from_message(m.get("body", ""))
            if otp:
                print(f"OTP পাওয়া গেল: {otp}")
                return enter_otp_in_browser(driver, otp)
        time.sleep(5)
    print("OTP পাওয়া যায়নি – টাইমআউট")
    return False

def enter_otp_in_browser(driver, otp):
    """ব্রাউজারে OTP টাইপ করে সাবমিট"""
    try:
        # OTP ইনপুট ফিল্ডগুলো
        otp_fields = WebDriverWait(driver, 15).until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@type='tel']"))
        )
        if len(otp_fields) == 1:
            otp_fields[0].clear()
            otp_fields[0].send_keys(otp)
        else:
            for i, ch in enumerate(otp):
                if i < len(otp_fields):
                    otp_fields[i].send_keys(ch)
        time.sleep(1)

        # সাবমিট
        verify_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        verify_btn.click()
        print("OTP সাবমিট হয়েছে।")
        return True
    except Exception as e:
        print(f"OTP ইনপুটে ব্যর্থ: {e}")
        driver.save_screenshot("otp_error.png")
        return False

def run_bot():
    print("===== Instagram Auto Signup Bot (Enhanced) =====")
    try:
        fullname = input("নাম: ").strip()
        pwd = input("পাসওয়ার্ড: ").strip()
        if not fullname or not pwd:
            print("নাম ও পাসওয়ার্ড উভয়ই প্রয়োজন।")
            return

        # ১. ইমেইল
        print("\n[১] ইমেইল তৈরি হচ্ছে…")
        inbox = create_email()
        if not inbox:
            print("ইমেইল তৈরি ব্যর্থ।")
            return
        print(f"ইমেইল: {inbox['address']}")

        # ২. ব্রাউজার
        print("[২] ব্রাউজার চালু হচ্ছে…")
        driver = setup_driver()
        if not driver:
            return

        # ৩. সাইন‑আপ
        print("[৩] সাইন‑আপ ফর্ম পূরণ হচ্ছে…")
        if not perform_instagram_signup(driver, inbox['address'], fullname, pwd):
            input("\nসাইন‑আপ ব্যর্থ। স্ক্রিনশট দেখুন এবং Enter চাপুন বন্ধ করতে।")
            return

        # ৪. OTP
        print("[৪] OTP যাচাই হচ্ছে (২ মিনিট)…")
        if handle_otp_verification(driver, inbox):
            print("\n===== সফল! অ্যাকাউন্ট তৈরি হলো =====")
            print(f"ইমেইল: {inbox['address']}")
            print(f"পাসওয়ার্ড: {pwd}")
            input("\nব্রাউজার বন্ধ করতে Enter চাপুন…")
        else:
            print("\nOTP যাচাই ব্যর্থ।")
    except Exception as e:
        print(f"ক্রিটিক্যাল ত্রুটি: {e}")
    finally:
        if 'driver' in locals() and driver:
            driver.quit()

if __name__ == "__main__":
    run_bot()
