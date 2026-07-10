import os
import sys
import time
import random
import json
import requests

def checkin():
    # 1. 随机延时 1 到 1800 秒（支持 SKIP_DELAY 环境变量，方便测试）
    if os.environ.get("SKIP_DELAY") == "true":
        print("Skipping delay due to SKIP_DELAY environment variable.")
    else:
        delay = random.randint(1, 1800)
        print(f"Waiting for {delay} seconds before starting check-in logic...")
        time.sleep(delay)
    print("Resuming check-in...")

    url_login = "https://dangao.iisbo.com/api/login"
    url_checkin = "https://dangao.iisbo.com/api/user/checkin"
    
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    # 读取 Token 缓存
    token_cache_dir = ".token_cache"
    token_cache_path = os.path.join(token_cache_dir, "token.txt")
    user_token = None

    if os.path.exists(token_cache_path):
        try:
            with open(token_cache_path, "r", encoding="utf-8") as f:
                user_token = f.read().strip()
            print(f"Loaded token from cache file: {token_cache_path}")
        except Exception as e:
            print(f"Error reading token cache file: {e}")

    if not user_token:
        user_token = os.environ.get("USER_TOKEN")
        if user_token:
            print("Fallback to USER_TOKEN from environment.")
        else:
            print("No cached token or environment token found.")

    need_login = False

    # 2. 如果存在 Token，先尝试直接进行签到
    if user_token:
        print("Attempting to check in directly with existing token...")
        checkin_headers = headers.copy()
        checkin_headers["Authorization"] = f"Bearer {user_token}"
        try:
            checkin_response = requests.post(url_checkin, headers=checkin_headers)
            status_code = checkin_response.status_code
            print(f"Direct Checkin Status Code: {status_code}")
            
            if status_code == 200:
                print("签到成功！")
                sys.exit(0)
            elif status_code == 400:
                print("今天已签到或已完成，退出程序。")
                sys.exit(0)
            elif status_code == 401:
                print("Token is invalid or expired (401 Unauthorized). Will login to obtain a new token.")
                need_login = True
            else:
                # 其它状态码
                print(f"Direct Checkin failed with status code {status_code}.")
                sys.exit(1)
        except Exception as e:
            print(f"Error during direct checkin: {e}.")
            sys.exit(1)
    else:
        need_login = True

    # 3. 如果 Token 不存在，或者使用该 Token 请求时接口返回了 401
    if need_login:
        print("Proceeding to login and obtain a new token...")
        email = os.environ.get("USER_EMAIL")
        password = os.environ.get("USER_PASSWORD")
        
        if not email or not password:
            print("Error: USER_EMAIL or USER_PASSWORD environment variables not set.")
            sys.exit(1)
            
        payload = {
            "email": email,
            "password": password,
            "remember_me": 7
        }
        
        try:
            print("--- Sending Login Request ---")
            response = requests.post(url_login, headers=headers, json=payload)
            print(f"Login Status Code: {response.status_code}")
            res_json = response.json()
            
            token = res_json.get("token")
            if not token:
                print("Failed to get token from login response. Check username/password.")
                print(f"Response: {res_json}")
                sys.exit(1)
            
            # 创建缓存目录（如果不存在）并将新 Token 写入本地文件 .token_cache/token.txt
            if not os.path.exists(token_cache_dir):
                os.makedirs(token_cache_dir, exist_ok=True)
            with open(token_cache_path, "w", encoding="utf-8") as f:
                f.write(token.strip())
            print(f"Successfully generated and wrote new token to {token_cache_path}")
            
            # 使用新 Token 重新发送签到请求
            checkin_headers = headers.copy()
            checkin_headers["Authorization"] = f"Bearer {token}"
            
            print("\n--- Sending Checkin Request with new token ---")
            checkin_response = requests.post(url_checkin, headers=checkin_headers)
            print(f"Checkin Status Code: {checkin_response.status_code}")
            checkin_json = checkin_response.json()
            print("Checkin Response JSON:")
            print(json.dumps(checkin_json, indent=4, ensure_ascii=False))
            
            if checkin_response.status_code == 200:
                print("\n签到成功！")
                sys.exit(0)
            elif checkin_response.status_code == 400:
                print("\n今天已签到或已完成，退出程序。")
                sys.exit(0)
            else:
                print(f"\n签到失败，状态码: {checkin_response.status_code}，响应信息: {checkin_json}")
                sys.exit(1)
                
        except Exception as e:
            print(f"\n运行出错: {e}")
            sys.exit(1)

if __name__ == "__main__":
    checkin()
