import os
import sys
import time
import random
import json
import requests

RETRYABLE_STATUSES = {502, 503, 504}
MAX_RETRIES = 3
RETRY_INTERVAL = 60  # seconds


def do_request_with_retry(method, url, headers, json_payload=None, label="request"):
    """带重试的 HTTP 请求封装。对 5xx 自动重试最多 MAX_RETRIES 次。
    返回 (response, exhausted) —— exhausted 为 True 表示重试耗尽仍失败。"""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            if method == "POST":
                resp = requests.post(url, headers=headers, json=json_payload)
            else:
                resp = requests.get(url, headers=headers)

            if resp.status_code in RETRYABLE_STATUSES:
                print(f"[{label}] 收到 {resp.status_code}（第 {attempt}/{MAX_RETRIES} 次尝试），"
                      f"{RETRY_INTERVAL} 秒后重试...")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_INTERVAL)
                continue
            return resp, False
        except requests.RequestException as e:
            print(f"[{label}] 网络异常: {e}（第 {attempt}/{MAX_RETRIES} 次尝试）")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_INTERVAL)
            continue

    print(f"[{label}] 重试 {MAX_RETRIES} 次后仍失败，放弃。")
    return None, True


def checkin():
    # 1. 随机延时
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    token_cache_dir = ".token_cache"
    token_cache_path = os.path.join(token_cache_dir, "token.txt")
    user_token = None

    # 2. 读取 Token 缓存
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

    # 3. 如果存在 Token，尝试直接签到（带重试）
    if user_token:
        print("Attempting to check in directly with existing token...")
        checkin_headers = headers.copy()
        checkin_headers["Authorization"] = f"Bearer {user_token}"

        resp, exhausted = do_request_with_retry(
            "POST", url_checkin, checkin_headers, label="直接签到"
        )

        if resp is not None:
            status_code = resp.status_code
            print(f"Direct Checkin Status Code: {status_code}")

            if status_code == 200:
                print("签到成功！")
                sys.exit(0)
            elif status_code == 400:
                try:
                    body = resp.json()
                    if body.get("error") == "今天已经签到过了":
                        print("今天已签到，退出程序。")
                        sys.exit(0)
                except Exception:
                    pass
                print("签到返回 400，退出程序。")
                sys.exit(0)
            elif status_code == 401:
                print("Token is invalid or expired (401). Will login to obtain a new token.")
                # 继续走登录流程
            else:
                print(f"Direct Checkin returned unexpected status {status_code}, "
                      f"falling back to login flow...")
                # 非 5xx 也兜底走登录
        else:
            # 5xx 重试耗尽
            print("Direct checkin failed after retries (server 5xx). "
                  "Falling back to login to get a fresh token and retry...")

    # 4. 登录
    print("Proceeding to login and obtain a new token...")
    email = os.environ.get("USER_EMAIL")
    password = os.environ.get("USER_PASSWORD")

    if not email or not password:
        print("Error: USER_EMAIL or USER_PASSWORD environment variables not set.")
        sys.exit(1)

    login_payload = {"email": email, "password": password, "remember_me": 7}

    resp, exhausted = do_request_with_retry(
        "POST", url_login, headers, json_payload=login_payload, label="登录"
    )

    if resp is None:
        print("Login failed after all retries (server unavailable). Exiting.")
        sys.exit(1)

    print(f"Login Status Code: {resp.status_code}")
    if resp.status_code != 200:
        print(f"Login failed with status {resp.status_code}: {resp.text}")
        sys.exit(1)

    res_json = resp.json()
    new_token = res_json.get("token")
    if not new_token:
        print(f"Failed to get token from login response: {res_json}")
        sys.exit(1)

    # 写入缓存
    if not os.path.exists(token_cache_dir):
        os.makedirs(token_cache_dir, exist_ok=True)
    with open(token_cache_path, "w", encoding="utf-8") as f:
        f.write(new_token.strip())
    print(f"Successfully wrote new token to {token_cache_path}")

    # 5. 用新 Token 签到（带重试）
    checkin_headers = headers.copy()
    checkin_headers["Authorization"] = f"Bearer {new_token}"

    print("\n--- Sending Checkin Request with new token ---")
    resp, exhausted = do_request_with_retry(
        "POST", url_checkin, checkin_headers, label="新Token签到"
    )

    if resp is None:
        print("Checkin failed after all retries (server unavailable). "
              "Token has been cached for next run. Exiting.")
        sys.exit(1)

    print(f"Checkin Status Code: {resp.status_code}")
    try:
        checkin_json = resp.json()
        print("Checkin Response JSON:")
        print(json.dumps(checkin_json, indent=4, ensure_ascii=False))
    except Exception:
        print(f"Checkin response (non-JSON): {resp.text}")

    if resp.status_code == 200:
        print("\n签到成功！")
        sys.exit(0)
    elif resp.status_code == 400:
        print("\n今天已签到或已完成，退出程序。")
        sys.exit(0)
    else:
        print(f"\n签到失败，状态码: {resp.status_code}")
        sys.exit(1)


if __name__ == "__main__":
    checkin()