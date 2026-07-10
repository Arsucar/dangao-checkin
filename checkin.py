import os
import sys
import time
import random
import json
import requests

def checkin():
    # 1. Random delay between 1 and 1800 seconds
    delay = random.randint(1, 1800)
    print(f"Waiting for {delay} seconds before starting check-in logic...")
    time.sleep(delay)
    print("Resuming check-in...")

    # 2. Read environmental variables
    email = os.environ.get("USER_EMAIL")
    password = os.environ.get("USER_PASSWORD")
    
    if not email or not password:
        print("Error: USER_EMAIL or USER_PASSWORD environment variables not set.")
        sys.exit(1)
        
    url_login = "https://dangao.iisbo.com/api/login"
    url_checkin = "https://dangao.iisbo.com/api/user/checkin"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    payload = {
        "email": email,
        "password": password,
        "remember_me": 7
    }
    
    print("--- Sending Login Request ---")
    try:
        response = requests.post(url_login, headers=headers, json=payload)
        print(f"Login Status Code: {response.status_code}")
        res_json = response.json()
        print("Login Response JSON:")
        print(json.dumps(res_json, indent=4, ensure_ascii=False))
        
        token = res_json.get("token")
        if not token:
            print("Failed to get token from response. Check username/password.")
            sys.exit(1)
        
        checkin_headers = headers.copy()
        checkin_headers["Authorization"] = f"Bearer {token}"
        
        print("\n--- Sending Checkin Request ---")
        checkin_response = requests.post(url_checkin, headers=checkin_headers)
        print(f"Checkin Status Code: {checkin_response.status_code}")
        checkin_json = checkin_response.json()
        print("Checkin Response JSON:")
        print(json.dumps(checkin_json, indent=4, ensure_ascii=False))
        
        if checkin_response.status_code == 200:
            print("\n签到成功！")
        elif checkin_response.status_code == 400 and checkin_json.get("error") == "今天已经签到过了":
            print("\n今天已经签到过了（重复签到）。")
        else:
            print(f"\n签到失败，状态码: {checkin_response.status_code}，响应信息: {checkin_json}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n运行出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    checkin()
