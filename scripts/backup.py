#!/usr/bin/env python3
"""
豆包聊天记录自动备份工具
借鉴 DeepSeek Chat Backup 设计，支持 PII 脱敏、限速、增量去重。
"""

import json
import os
import re
import sys
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path

import yaml
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By


BACKUP_DIR = Path(os.path.expanduser("~/doubao-backups"))
BROWSER_DATA = BACKUP_DIR / ".browser_data"
STATE_FILE = BACKUP_DIR / ".backup_state.json"
COOKIE_FILE = BACKUP_DIR / "cookies.json"


# ========== PII 脱敏 ==========

PII_PATTERNS = {
    "phone": (r'1[3-9]\d{9}', lambda m: m.group()[:3] + "****" + m.group()[-4:]),
    "email": (r'[\w.+-]+@[\w-]+\.[\w.]+', lambda m: m.group()[:2] + "***@" + m.group().split("@")[1]),
    "id_card": (r'\d{17}[\dXx]', lambda m: m.group()[:6] + "********" + m.group()[-4:]),
    "bank_card": (r'\d{16,19}', lambda m: m.group()[:4] + " **** **** " + m.group()[-4:]),
    "ip_addr": (r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', lambda m: m.group()[:m.group().rfind(".")] + ".xxx"),
    "api_key": (r'(token|key|secret|password|api_key)=\S+', 
                lambda m: m.group().split("=")[0] + "=***REDACTED***" if "=" in m.group() else m.group()),
}


def desensitize_pii(text, enabled=True):
    if not enabled or not text:
        return text
    for name, (pattern, replacer) in PII_PATTERNS.items():
        text = re.sub(pattern, replacer, text)
    return text


def desensitize_chat(chat, enabled=True):
    if not enabled:
        return chat
    result = chat.copy()
    result["title"] = desensitize_pii(chat.get("title", ""))
    result["messages"] = [{"role": m.get("role", "unknown"), "content": desensitize_pii(m.get("content", ""))} for m in chat.get("messages", [])]
    return result


# ========== 增量去重 ==========

def compute_content_hash(messages):
    content = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


# ========== 限速控制 ==========

class RateLimiter:
    def __init__(self, min_interval=2.0, max_retries=3):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.last_request_time = 0
    
    def wait(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request_time = time.time()
    
    def retry(self, func, *args, **kwargs):
        for attempt in range(self.max_retries):
            try:
                self.wait()
                return func(*args, **kwargs)
            except Exception as e:
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"[!] 请求失败，{wait_time}秒后重试... ({attempt+1}/{self.max_retries})")
                    time.sleep(wait_time)
                else:
                    raise e


# ========== 配置 ==========

def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_backup_time": None, "chat_ids": {}}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ========== 浏览器 ==========

def create_driver(headless=False, login_mode=False):
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    if login_mode:
        BROWSER_DATA.mkdir(parents=True, exist_ok=True)
        options.add_argument(f"--user-data-dir={BROWSER_DATA}")

    chrome = "/snap/chromium/current/usr/lib/chromium-browser/chrome"
    chromedriver = "/snap/chromium/current/usr/lib/chromium-browser/chromedriver"
    if os.path.exists(chrome):
        options.binary_location = chrome
        service = Service(executable_path=chromedriver)
        driver = webdriver.Chrome(service=service, options=options)
    else:
        driver = webdriver.Chrome(options=options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
    })
    return driver


def is_logged_in(driver):
    try:
        # 豆包登录后会有聊天输入框
        inputs = driver.find_elements(By.CSS_SELECTOR, 'textarea, div[contenteditable="true"], input[type="text"]')
        for inp in inputs:
            if inp.is_displayed():
                # 进一步检查是否在聊天页面
                url = driver.current_url
                if "chat" in url or "doubao" in url:
                    return True
    except:
        pass
    return False


# ========== 抓取 ==========

def scrape_chat_list(driver):
    """抓取豆包聊天列表。豆包的聊天列表在左侧侧边栏。"""
    chats = []
    time.sleep(3)
    
    try:
        # 豆包的聊天列表选择器（需要根据实际页面调整）
        chats = driver.execute_script("""
            const chats = [];
            
            // 尝试多种选择器
            const selectors = [
                // 豆包可能的聊天列表选择器
                'div[class*="conversation"] div[class*="item"]',
                'div[class*="chat-list"] div',
                'div[class*="sidebar"] a',
                'div[class*="session"] div',
                'ul li a[href*="chat"]',
                // 通用选择器
                '[class*="history"] div',
                '[class*="recent"] div',
            ];
            
            for (const sel of selectors) {
                const items = document.querySelectorAll(sel);
                if (items.length > 0) {
                    items.forEach(item => {
                        const text = item.innerText.trim();
                        const href = item.getAttribute('href') || '';
                        if (text && text.length > 1 && text.length < 100) {
                            chats.push({
                                chat_id: href.includes('/') ? href.split('/').pop() : '',
                                title: text.substring(0, 100),
                                href: href
                            });
                        }
                    });
                    if (chats.length > 0) break;
                }
            }
            
            // 如果上面没找到，尝试更通用的方式
            if (chats.length === 0) {
                // 查找所有可点击的文本元素
                document.querySelectorAll('div, span, a').forEach(el => {
                    const text = el.innerText.trim();
                    const rect = el.getBoundingClientRect();
                    // 只要左侧边栏的元素（x < 300）
                    if (text && text.length > 2 && text.length < 50 && rect.x < 300 && rect.width > 50) {
                        const href = el.getAttribute('href') || '';
                        chats.push({
                            chat_id: href ? href.split('/').pop() : '',
                            title: text,
                            href: href
                        });
                    }
                });
            }
            
            return chats;
        """) or []
    except Exception as e:
        print(f"[!] 抓取聊天列表失败: {e}")
    
    if chats:
        print(f"[i] 找到 {len(chats)} 个聊天")
    return chats


def scrape_chat_content(driver, chat_url):
    """抓取单个聊天的消息内容。"""
    try:
        driver.get(chat_url)
        time.sleep(5)  # 等待页面加载
        
        # 滚动加载所有消息
        for _ in range(20):
            prev = driver.execute_script("return document.body.scrollHeight")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            if driver.execute_script("return document.body.scrollHeight") == prev:
                break
        
        # 抓取消息内容
        messages = driver.execute_script("""
            const msgs = [];
            
            // 豆包的消息选择器（需要根据实际页面调整）
            const selectors = [
                'div[class*="message"]',
                'div[class*="chat-message"]',
                'div[class*="bubble"]',
                'div[class*="content"]',
                '[data-testid*="message"]',
            ];
            
            let els = [];
            for (const sel of selectors) {
                els = document.querySelectorAll(sel);
                if (els.length > 0) break;
            }
            
            els.forEach(el => {
                const text = el.innerText.trim();
                if (!text || text.length < 2) return;
                
                const cls = el.className || '';
                let role = 'unknown';
                
                // 豆包的消息角色判断
                if (cls.includes('user') || cls.includes('human') || cls.includes('self')) {
                    role = 'user';
                } else if (cls.includes('assistant') || cls.includes('bot') || cls.includes('ai') || cls.includes('doubao')) {
                    role = 'assistant';
                } else {
                    // 根据位置判断
                    const allMsgs = document.querySelectorAll('[class*="message"], [class*="bubble"]');
                    const idx = Array.from(allMsgs).indexOf(el);
                    role = idx % 2 === 0 ? 'user' : 'assistant';
                }
                
                msgs.push({ role, content: text });
            });
            
            return msgs;
        """)
        
        return messages or []
        
    except Exception as e:
        print(f"[✗] 抓取失败: {e}")
        return []


# ========== 登录 ==========

def do_login():
    """打开浏览器让用户登录豆包。"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    
    print("=" * 50)
    print("豆包登录")
    print("=" * 50)
    print("浏览器即将打开豆包...")
    print("请手动登录你的豆包帐号")
    print()
    
    driver = create_driver(headless=False, login_mode=True)
    driver.get("https://www.doubao.com")
    
    print("等待登录... (最长 5 分钟)")
    start = time.time()
    while time.time() - start < 300:
        try:
            if is_logged_in(driver):
                print("[✓] 登录成功！保存 session...")
                # 保存 cookie
                cookies = driver.get_cookies()
                with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, ensure_ascii=False, indent=2)
                print(f"[✓] Cookie 已保存: {COOKIE_FILE}")
                driver.quit()
                print("完成！现在可以运行备份了：")
                print("  python3 scripts/backup.py --full")
                return True
        except:
            pass
        time.sleep(3)
    
    print("[✗] 超时")
    driver.quit()
    return False


# ========== 备份 ==========

def do_backup(full=False, pii=False, rate_limit=2.0):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    state = load_state()
    is_first = not state.get("last_backup_time")
    
    if is_first and not COOKIE_FILE.exists():
        return do_login()
    
    print(f"{'='*50}")
    print(f"豆包聊天记录备份")
    print(f"模式: {'全量' if full or is_first else '增量'}")
    print(f"PII脱敏: {'开启' if pii else '关闭'}")
    print(f"限速: {rate_limit}秒/请求")
    if state.get("last_backup_time"):
        print(f"上次: {state['last_backup_time']}")
    print(f"{'='*50}\n")
    
    # 尝试登录
    driver = create_driver(headless=True, login_mode=True)
    driver.get("https://www.doubao.com")
    time.sleep(5)
    
    if not is_logged_in(driver):
        # 尝试用 cookie
        if COOKIE_FILE.exists():
            try:
                with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                for c in cookies:
                    for k in ["sameSite", "storeId", "id"]:
                        c.pop(k, None)
                    try:
                        driver.add_cookie(c)
                    except:
                        pass
                driver.get("https://www.doubao.com")
                time.sleep(3)
            except:
                pass
    
    if not is_logged_in(driver):
        driver.quit()
        print("[✗] 未登录，请先运行:")
        print("  python3 scripts/backup.py --login")
        return
    
    print("[✓] 已登录")
    
    # 抓取聊天列表
    print("\n[i] 抓取聊天列表...")
    chat_list = scrape_chat_list(driver)
    if not chat_list:
        print("[✗] 未找到聊天记录")
        driver.quit()
        return
    
    existing_chats = {}
    existing_dir = BACKUP_DIR / "json"
    existing_dir.mkdir(exist_ok=True)
    for f in existing_dir.glob("*.json"):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                existing_chats[data.get("chat_id", f.stem)] = data
        except:
            pass
    
    limiter = RateLimiter(min_interval=rate_limit)
    new_chats = []
    updated = 0
    skipped = 0
    
    for i, chat in enumerate(chat_list):
        chat_id = chat.get("chat_id") or hashlib.md5(chat["title"].encode()).hexdigest()[:12]
        title = chat["title"]
        
        # 增量去重
        if not full and chat_id in existing_chats:
            existing = existing_chats[chat_id]
            if existing.get("title") == title and existing.get("content_hash"):
                skipped += 1
                continue
        
        print(f"[{i+1}/{len(chat_list)}] {title[:50]}...")
        
        chat_url = chat.get("href", "")
        if chat_url and not chat_url.startswith("http"):
            chat_url = "https://www.doubao.com" + chat_url
        elif not chat_url:
            chat_url = f"https://www.doubao.com/chat/{chat_id}"
        
        try:
            messages = limiter.retry(scrape_chat_content, driver, chat_url)
        except Exception as e:
            print(f"[✗] 抓取失败: {e}")
            continue
        
        content_hash = compute_content_hash(messages)
        
        chat_data = {
            "chat_id": chat_id,
            "title": title,
            "url": chat_url,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "content_hash": content_hash,
            "messages": messages,
        }
        
        if chat_id in existing_chats:
            updated += 1
        else:
            new_chats.append(chat_data)
        
        save_data = desensitize_chat(chat_data, enabled=pii) if pii else chat_data
        safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in chat_id)[:60]
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:50]
        with open(existing_dir / f"{safe_id}_{safe_title}.json", "w", encoding="utf-8") as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    driver.quit()
    
    state["last_backup_time"] = datetime.now(timezone.utc).isoformat()
    for chat in new_chats:
        state["chat_ids"][chat["chat_id"]] = chat["title"]
    save_state(state)
    
    print(f"\n{'='*50}")
    print(f"完成! 新增 {len(new_chats)} / 更新 {updated} / 跳过 {skipped} / 总计 {len(state['chat_ids'])}")
    print(f"{'='*50}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="豆包备份")
    parser.add_argument("--full", "-f", action="store_true", help="全量备份")
    parser.add_argument("--login", action="store_true", help="登录")
    parser.add_argument("--pii", action="store_true", help="PII 脱敏")
    parser.add_argument("--rate-limit", type=float, default=2.0, help="请求间隔秒数")
    args = parser.parse_args()
    
    if args.login:
        do_login()
    else:
        do_backup(full=args.full, pii=args.pii, rate_limit=args.rate_limit)


if __name__ == "__main__":
    main()
