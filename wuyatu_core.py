"""
无涯图片爬取工具 v8
==================
百度图片搜索 -> 原图+CDN双源下载 -> 桌面/爬取的图片/关键词/
循环运行 | 关键词命名 | 默认10张 | 自动去重 | 动态补图 | 脏JSON修复
"""

import os, re, sys, time, json, hashlib, shutil, urllib.parse, requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== 终端 ====================
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    TERM_WIDTH = shutil.get_terminal_size().columns or 60
except Exception:
    TERM_WIDTH = 60

# ==================== 常量 ====================
TIMEOUT = 18
DOWNLOAD_WORKERS = 12
RETRIES_PER_IMG = 3
PAGE_DELAY = 0.4
MAX_BAIDU_PAGES = 20  # 绝对上限, 实际页数由需求量动态决定
DEFAULT_COUNT = 10
URL_POOL_MULTIPLIER = 10   # 搜到的URL数 = 需求量 x 10, 保证下载时有得筛
MIN_IMAGE_KB = 8
# ==============================================

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
})

DOWNLOADED_URL_SIGS = set()  # 全局去重池


# ==================== 日志钩子 ====================

_log_func = None  # GUI 模式下替换为 queue.put 回调

def _emit(msg: str, *, level: str = "info"):
    """统一日志出口：CLI 模式自动回退到 print"""
    if _log_func is not None:
        _log_func(msg, level)
    else:
        print(msg)

# ==================== 工具 ====================

def get_desktop_path() -> Path:
    up = os.environ.get("USERPROFILE", "") or os.environ.get("HOME", "")
    if up:
        for name in ("Desktop", "桌面"):
            p = Path(up) / name
            if p.exists():
                return p
    return Path.home() / "Desktop"


def url_sig(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:16]


def clear_line():
    print("\r" + " " * (TERM_WIDTH - 1) + "\r", end="")


def print_bar(prefix: str, done: int, total: int, suffix: str = ""):
    bar_len = max(10, TERM_WIDTH - len(prefix) - len(suffix) - 10)
    filled = int(bar_len * done / total) if total > 0 else 0
    bar = "█" * filled + "─" * (bar_len - filled)
    pct = done * 100 // total if total > 0 else 0
    clear_line()
    print(f"\r{prefix} {bar} {pct}% {suffix}", end="", flush=True)


def hr(char: str = "─"):
    print(char * min(TERM_WIDTH, 60))


def clean_json(text: str) -> str:
    """清理百度返回的脏JSON: 控制字符 + 非标准转义(如 \\s \\g)"""
    # Step 1: 删除控制字符 (保留 \t \n \r)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
    # Step 2: 把无效JSON转义(\\后面跟的不是 "/\\bfnrtu) 变成双反斜杠
    text = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)
    return text


def banner():
    print()
    print("  ┌──────────────────────────────────┐")
    print("  │                                  │")
    print("  │    ·  ·  ·  ·  ·  ·  ·  ·  ·     │")
    print("  │                                  │")
    print("  │          无          涯          │")
    print("  │          ─────────────           │")
    print("  │          图片爬取工具             │")
    print("  │          百度图片下载             │")
    print("  │                                  │")
    print("  │       QQ: 1246792122             │")
    print("  │                                  │")
    print("  └──────────────────────────────────┘")
    print()


# ==================== 下载引擎 ====================

def download_one(orig_url: str, fallback_url: str, folder: Path, idx: int) -> tuple:
    """
    下载单张。优先原图, 失败自动切CDN中图。
    返回 (idx, success, message)
    """
    urls = [orig_url]
    if fallback_url and fallback_url != orig_url:
        urls.append(fallback_url)

    for u in urls:
        for attempt in range(1, RETRIES_PER_IMG + 1):
            try:
                r = SESSION.get(u, timeout=TIMEOUT, stream=True)
                r.raise_for_status()

                name = f"_tmp_{idx:05d}.jpg"
                path = folder / name

                with open(path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)

                size = path.stat().st_size
                if size < MIN_IMAGE_KB * 1024:
                    path.unlink()
                    break  # 太小, 换下一个URL

                sz = f"{size / (1024*1024):.1f}MB" if size >= 1024*1024 else f"{size // 1024}KB"
                return idx, True, sz

            except Exception:
                if attempt < RETRIES_PER_IMG:
                    time.sleep(0.3)
                else:
                    break

    return idx, False, "失败"


# ==================== 搜索 ====================

def _ensure_baidu_cookies():
    try:
        SESSION.get("https://image.baidu.com/", timeout=10)
    except Exception:
        pass


def _extract_urls(item: dict) -> tuple:
    """
    从百度条目中提取 (原图URL, CDN中图URL)。
    原图: replaceUrl[0].ObjURL (来自源站, 可能防盗链)
    CDN:  middleURL (百度CDN, 稳定但可能尺寸小)
    """
    orig = ""
    cdn = ""

    ru = item.get("replaceUrl")
    if ru:
        if isinstance(ru, str):
            try:
                ru = json.loads(ru)
            except Exception:
                pass
        if isinstance(ru, list) and len(ru) > 0:
            first = ru[0]
            if isinstance(first, dict):
                orig = first.get("ObjURL", "") or ""
            elif isinstance(first, str):
                orig = first
        elif isinstance(ru, dict):
            orig = ru.get("ObjURL", "") or ""

    for key in ("middleURL", "hoverURL", "thumbURL"):
        u = item.get(key, "")
        if u.startswith("http"):
            cdn = u
            break

    if not orig.startswith("http"):
        orig = cdn
    if not cdn.startswith("http"):
        cdn = orig

    return orig, cdn


def baidu_search(keyword: str, want_count: int, log_cb=None) -> list:
    """返回 [(原图URL, CDN备用URL), ...]"""
    global _log_func
    if log_cb is not None:
        _log_func = log_cb
    results = []
    seen = set()
    api = "https://image.baidu.com/search/acjson"
    empty_streak = 0

    # 动态计算搜索页数: 每页约30条, 目标3倍需求量的URL池, 最少3页最多20页
    max_pages = max(3, min(MAX_BAIDU_PAGES, (want_count * 3 + 29) // 30))

    for page in range(max_pages):
        params = {
            "tn": "resultjson_com",
            "logid": str(int(time.time() * 1000) % 10000000000),
            "ipn": "rj", "ct": "201326592", "is": "",
            "fp": "result", "cl": "2", "lm": "-1",
            "ie": "utf-8", "oe": "utf-8",
            "word": keyword, "queryWord": keyword,
            "pn": page * 30, "rn": 30,
            "gsm": hex(page * 30)[2:] if page > 0 else "0",
        }

        try:
            r = SESSION.get(api, params=params, timeout=TIMEOUT,
                           headers={"Referer": "https://image.baidu.com/"})
            data = json.loads(clean_json(r.text))
        except Exception as e:
            _emit(f"  ! 第{page+1}页JSON异常: {e}", level="warning")
            time.sleep(1)
            try:
                r = SESSION.get(api, params=params, timeout=TIMEOUT,
                               headers={"Referer": "https://image.baidu.com/"})
                data = json.loads(clean_json(r.text))
            except Exception:
                empty_streak += 1
                if empty_streak >= 2:
                    break
                continue

        if data.get("antiFlag") or "Forbid spider" in str(data):
            _emit("  ! 触发反爬, 重新授权...", level="warning")
            _ensure_baidu_cookies()
            time.sleep(1.5)
            try:
                r = SESSION.get(api, params=params, timeout=TIMEOUT,
                               headers={"Referer": "https://image.baidu.com/"})
                data = json.loads(clean_json(r.text))
            except Exception:
                break

        items = data.get("data", [])
        if not items:
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue

        raw_count = 0   # 百度返回的有效URL数（去重前）
        page_count = 0  # 去重后的新URL数
        skip_words = ["afxbackupsimgurl", "bgimgurl", "imgurl_",
                      "favicon", "icon.svg", "1x1", "64x64", "/img/baidu"]

        for item in items:
            if not isinstance(item, dict):
                continue
            orig, cdn = _extract_urls(item)
            if not orig.startswith("http"):
                continue
            if any(w in orig.lower() for w in skip_words):
                continue
            raw_count += 1

            sig = url_sig(orig)
            if sig in DOWNLOADED_URL_SIGS or sig in seen:
                continue
            seen.add(sig)

            results.append((orig, cdn))
            page_count += 1

        _emit(f"  第{page+1}页 +{page_count}张 (原始{raw_count}张), 累计 {len(results)} 对地址")

        # 仅当百度真没返回有效URL时才计为空页；全被去重不算空页
        if raw_count == 0:
            empty_streak += 1
            if empty_streak >= 2:
                break
            continue
        empty_streak = 0

        if len(results) >= want_count * URL_POOL_MULTIPLIER:
            break

        time.sleep(PAGE_DELAY)

    return results


# ==================== 主流程 ====================

def run_once(save_dir: Path | str | None = None) -> bool:
    print()

    # --- 关键词 ---
    while True:
        try:
            kw = input("  > 搜索关键词: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  再见!")
            return False
        if kw:
            break
        print("     ! 关键词不能为空!")

    # --- 数量 ---
    while True:
        try:
            raw = input(f"  > 下载数量 (默认{DEFAULT_COUNT}张, 1-200): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  再见!")
            return False
        if not raw:
            want = DEFAULT_COUNT
            print(f"     = 已设为默认 {DEFAULT_COUNT} 张")
            break
        try:
            want = int(raw)
            if 1 <= want <= 200:
                break
            print("     ! 请输入 1-200!")
        except ValueError:
            print("     ! 请输入有效的数字!")

    # --- 目录: 找已有目录或新建 ---
    if save_dir:
        base_dir = Path(save_dir)
    else:
        base_dir = get_desktop_path() / "无涯图片爬取"
    base_dir.mkdir(parents=True, exist_ok=True)
    # 查找是否已有该关键词的文件夹(可能带计数后缀)
    existing = list(base_dir.glob(f"{kw}*"))
    if existing:
        folder = existing[0]
    else:
        folder = base_dir / kw
    folder.mkdir(parents=True, exist_ok=True)

    # --- 搜索 ---
    print(f'\n  > 无涯搜索: "{kw}" ...')
    _ensure_baidu_cookies()
    pairs = baidu_search(kw, want)

    if not pairs:
        print(f"\n  X 未搜到图片, 请检查网络或换关键词。")
        return True

    total = len(pairs)
    print(f"\n  = 共获取 {total} 对图片地址 (已过滤重复)")

    # --- 下载 ---
    print(f"\n  > 保存至: {folder}")
    print(f"  > 命名: {kw}_0001 ~ {kw}_{want:04d}")
    print()

    ok = 0
    idx = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
        pending = {}

        # 首批
        for _ in range(min(DOWNLOAD_WORKERS, total)):
            if idx >= total:
                break
            orig, cdn = pairs[idx]
            fut = pool.submit(download_one, orig, cdn, folder, idx)
            pending[fut] = idx
            idx += 1

        while pending and ok < want:
            for fut in as_completed(pending):
                i, success, msg = fut.result()
                del pending[fut]

                if i < total:
                    DOWNLOADED_URL_SIGS.add(url_sig(pairs[i][0]))

                if success:
                    ok += 1

                elapsed = time.time() - start_time
                spd = f"{ok / elapsed:.1f}张/s" if elapsed > 0 else ""
                print_bar(f"  [{ok}/{want}]", ok, want, spd)

                if ok >= want:
                    for f in pending:
                        f.cancel()
                    pending.clear()
                    break

                need = want - ok
                slots = max(0, min(DOWNLOAD_WORKERS, need * 4 + 3) - len(pending))
                for _ in range(slots):
                    if idx >= total:
                        break
                    orig, cdn = pairs[idx]
                    fut = pool.submit(download_one, orig, cdn, folder, idx)
                    pending[fut] = idx
                    idx += 1

                break

            if not pending:
                break

    # --- 续号重命名 ---
    existing_max = 0
    for f in folder.glob(f"{kw}_*"):
        m = re.match(rf"{re.escape(kw)}_(\d+)", f.stem)
        if m:
            existing_max = max(existing_max, int(m.group(1)))

    tmp_files = sorted(folder.glob("_tmp_*"), key=lambda f: f.stat().st_mtime)
    for f in tmp_files[want:]:
        try:
            f.unlink()
        except Exception:
            pass
    for i, f in enumerate(tmp_files[:want], existing_max + 1):
        new_name = folder / f"{kw}_{i:04d}.jpg"
        try:
            f.rename(new_name)
        except Exception:
            alt = folder / f"{kw}_{i:04d}_{int(time.time()) % 10000:04d}.jpg"
            try:
                f.rename(alt)
            except Exception:
                pass

    clear_line()

    # --- 统计总数并更新文件夹名 ---
    total_files = len(list(folder.glob(f"{kw}_*.jpg")))
    new_name = f"{kw}（{total_files}张）"
    new_folder = folder.parent / new_name
    if folder.name != new_name:
        try:
            folder.rename(new_folder)
            folder = new_folder
        except Exception:
            pass

    elapsed = time.time() - start_time

    print()
    hr("-")
    print(f"  = 无涯下载完成! {ok}/{want} 张 | {elapsed:.1f}秒 | {folder}")
    hr("-")

    if ok < want:
        print(f"  ! 源链接失效较多, 只下到 {ok} 张。可换关键词重试。")

    try:
        os.startfile(str(folder))
    except Exception:
        pass

    # --- 继续 ---
    print()
    while True:
        try:
            again = input("  > 继续搜索? (回车继续 / q 退出): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n  再见!")
            return False
        if again == "":
            return True
        if again in ("q", "n", "no", "quit", "exit"):
            print("  再见!")
            return False
        if again in ("y", "yes", "ok"):
            return True
        print("    回车继续, q 退出。")

    return True


# ==================== 入口 ====================

def main():
    banner()
    try:
        while run_once():
            pass
    except KeyboardInterrupt:
        print("\n\n  已中断, 再见!")
    except Exception as e:
        print(f"\n  X 异常: {e}")
        import traceback
        traceback.print_exc()

    try:
        input("\n  按回车键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()
