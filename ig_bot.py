#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, time, re, sys, json
import requests
from html import unescape
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import undetected_chromedriver as uc   # pip install undetected-chromedriver

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
API = "https://api.edu-mails.com/api"
SIGNUP_URL = "https://www.instagram.com/accounts/emailsignup/"
CHROMEDRIVER_PATH = "/data/data/com.termux/files/usr/bin/chromedriver"
CHROMIUM_PATH = "/data/data/com.termux/files/usr/bin/chromium-browser"

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def create_email():
    try:
        r = requests.post(
            f"{API}/emails/generate",
            json={"action": "random"},
            headers={"Accept": "application/json"},
            timeout=20
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "success":
            raise RuntimeError(data)
        email = data["data"]["email"]
        return {"address": email["address"], "uuid": email["uuid"]}
    except Exception as e:
        print(f"[!] ইমেইল জেনারেট করতে ব্যর্থ: {e}")
        return None


def fetch_inbox_messages(inbox_info):
    try:
        r = requests.get(
            f"{API}/emails/{inbox_info['uuid']}",
            headers={"Accept": "application/json"},
            timeout=20
        )
        r.raise_for_status()
        return r.json().get("data", {}).get("messages", [])
    except Exception as e:
        print(f"[!] ইনবক্স চেক করতে ব্যর্থ: {e}")
        return []


def extract_otp(msg):
    if not msg:
        return None
    txt = re.sub(r"<[^>]+>", " ", msg)
    txt = unescape(txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    m = re.search(r"\b(\d{6})\b", txt)
    return m.group(1) if m else None


def setup_driver():
    opts = uc.ChromeOptions()
    opts.binary_location = CHROMIUM_PATH
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    )
    try:
        driver = uc.Chrome(
            driver_executable_path=CHROMEDRIVER_PATH,
            options=opts,
            use_subprocess=True   # হেডলেস মোডে ডিটেকশন কমাতে
        )
        return driver
    except Exception as e:
        print(f"[!] ব্রাউজার চালু করতে ব্যর্থ: {e}")
        return None


# ------------------------------------------------------------------
# Core Flow
# ------------------------------------------------------------------
def perform_signup(driver, email, full_name, pwd, user_name, bday):
    """
    1. পূরণ: নাম, ইমেইল, পাসওয়ার্ড
    2. নতুন ফিল্ড: username, জন্মতারিখ
    3. সাবমিট
    """
    try:
        driver.get(SIGNUP_URL)
        wait = WebDriverWait(driver, 20)

        # 1. পূরণ ফিল্ড
        wait.until(EC.presence_of_element_located((By.NAME, "fullName")))

        driver.find_element(By.NAME, "fullName").clear()
        driver.find_element(By.NAME, "fullName").send_keys(full_name)

        driver.find_element(By.NAME, "email").clear()
        driver.find_element(By.NAME, "email").send_keys(email)

        driver.find_element(By.NAME, "password").clear()
        driver.find_element(By.NAME, "password").send_keys(pwd)

        # 2. নতুন ফিল্ড: username
        # username ফিল্ডের নাম এখনই 'username', placeholder "Username"
        wait.until(EC.presence_of_element_located((By.NAME, "username")))
        driver.find_element(By.NAME, "username").clear()
        driver.find_element(By.NAME, "username").send_keys(user_name)

        # 3. জন্ম তারিখ: day, month, year
        # তিনটি ড্রপডাউন আছে: day, month, year
        # এগুলো সাধারণত <select name="day">, <select name="month">, <select name="year">
        day_sel = driver.find_element(By.NAME, "day")
        month_sel = driver.find_element(By.NAME, "month")
        year_sel = driver.find_element(By.NAME, "year")

        day_sel.send_keys(bday["day"])
        month_sel.send_keys(bday["month"])
        year_sel.send_keys(bday["year"])

        # 4. সাবমিট বাটন (type="submit")
        submit_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        submit_btn.click()

        print("[+] সাইন‑আপ বাটন ক্লিক হয়েছে, OTP‑এর জন্য অপেক্ষা করছি…")
        return True

    except TimeoutException:
        print("[!] ফর্ম লোড হতে সময় নিয়েছে। স্ক্রিনশট: signup_error.png")
        driver.save_screenshot("signup_error.png")
        return False
    except Exception as e:
        print(f"[!] সাইন‑আপ ফর্মে ত্রুটি: {e}")
        driver.save_screenshot("signup_error.png")
        return False


def handle_otp(driver, inbox_info, timeout=120):
    start = time.time()
    while time.time() - start < timeout:
        msgs = fetch_inbox_messages(inbox_info)
        for m in msgs:
            if m.get("read"):
                continue
            otp = extract_otp(m.get("body", ""))
            if otp:
                print(f"[+] OTP পাওয়া গেছে: {otp}")
                return enter_otp(driver, otp)
        time.sleep(5)
    print("[!] OTP পাওয়া যায়নি – টাইমআউট")
    return False


def enter_otp(driver, otp):
    try:
        wait = WebDriverWait(driver, 15)
        otp_inputs = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//input[@type='tel']"))
        )
        if len(otp_inputs) == 1:
            otp_inputs[0].clear()
            otp_inputs[0].send_keys(otp)
        else:
            for i, ch in enumerate(otp):
                if i < len(otp_inputs):
                    otp_inputs[i].send_keys(ch)
        time.sleep(1)

        # সাবমিট
        verify_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']"))
        )
        verify_btn.click()
        print("[+] OTP সাবমিট হয়েছে।")
        return True
    except Exception as e:
        print(f"[!] OTP ইনপুটে ত্রুটি: {e}")
        driver.save_screenshot("otp_error.png")
        return False


def main():
    print("===== Instagram Auto‑Signup Bot (Full‑Feature) =====")
    try:
        full_name = input("পূর্ণ নাম: ").strip()
        pwd = input("পাসওয়ার্ড: ").strip()
        if not full_name or not pwd:
            print("[!] নাম ও পাসওয়ার্ড উভয়ই দিতে হবে।")
            return

        # 1. ইমেইল
        print("\n[1] ইমেইল তৈরি হচ্ছে…")
        inbox = create_email()
        if not inbox:
            print("[!] ইমেইল তৈরি ব্যর্থ।")
            return
        print(f"[1] ইমেইল: {inbox['address']}")

        # 2. ব্রাউজার
        print("[2] ব্রাউজার চালু হচ্ছে…")
        driver = setup_driver()
        if not driver:
            return

        # 3. ইউজারনেম ও জন্ম তারিখ জিজ্ঞাসা
        print("\n[+] নতুন ইনস্টাগ্রাম ফিল্ড:")
        username = input("ইউজারনেম (সর্বোচ্চ ১৫ অক্ষর, ছোট হাতের অক্ষর, সংখ্যা, আন্ডারস্কোর): ").strip()
        if not username:
            print("[!] ইউজারনেম আবশ্যক।")
            return
        print("জন্ম তারিখ (DD MM YYYY) দিন:")
        bday_str = input().strip()
        try:
            day, month, year = map(int, bday_str.split())
            birth = {"day": f"{day:02d}", "month": f"{month:02d}", "year": str(year)}
        except Exception:
            print("[!] ভুল জন্ম তারিখ ফরম্যাট।")
            return

        # 4. সাইন‑আপ
        print("\n[3] সাইন‑আপ ফর্ম পূরণ হচ্ছে…")
        if not perform_signup(driver, inbox["address"], full_name, pwd, username, birth):
            input("\nসাইন‑আপ ব্যর্থ। স্ক্রিনশট দেখুন এবং Enter চাপুন বন্ধ করতে।")
            return

        # 5. OTP
        print("[4] OTP যাচাই হচ্ছে (২ মিনিট)…")
        if handle_otp(driver, inbox):
            print("\n===== সফল! অ্যাকাউন্ট তৈরি হয়েছে =====")
            print(f"ইমেইল: {inbox['address']}")
            print(f"পাসওয়ার্ড: {pwd}")
            input("\nব্রাউজার বন্ধ করতে Enter চাপুন…")
        else:
            print("\n[!] OTP যাচাই ব্যর্থ।")
    except KeyboardInterrupt:
        print("\n[!] ব্যবহারকারী দ্বারা বন্ধ করা হয়েছে।")
    finally:
        if 'driver' in locals() and driver:
            driver.quit()


if __name__ == "__main__":
    main()
