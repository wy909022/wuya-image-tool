"""
无涯图片爬取工具 Android v3.0 - Flet 版
=========================================
Flet (Flutter) 移动端 — 完整中文支持
"""
import sys, os, time, queue, threading, re, importlib.util
from pathlib import Path

# ── 动态加载核心模块 ───────────────────────────
_core_path = Path(__file__).parent / "无涯图片爬取工具.py"
_spec = importlib.util.spec_from_file_location("wuyatu_core", _core_path)
_core = importlib.util.module_from_spec(_spec)
sys.modules["_core"] = _core
_spec.loader.exec_module(_core)

from _core import (  # noqa: E402
    baidu_search, download_one, _ensure_baidu_cookies,
    get_desktop_path, url_sig,
    DOWNLOADED_URL_SIGS, DOWNLOAD_WORKERS, TIMEOUT,
    RETRIES_PER_IMG, DEFAULT_COUNT, URL_POOL_MULTIPLIER,
    SESSION, _emit, _log_func,
)
from concurrent.futures import ThreadPoolExecutor, as_completed

import flet as ft

# ── Android 存储 ──────────────────────────────
try:
    from android.storage import primary_external_storage_path
    ANDROID_SAVE = Path(primary_external_storage_path()) / "Download" / "无涯图片"
except Exception:
    # Windows/Mac 测试用 → 用户目录下的"下载/无涯图片"
    ANDROID_SAVE = Path.home() / "Downloads" / "无涯图片"


class WuyatuApp:
    """无涯图片爬取工具 — Flet 移动端"""

    def __init__(self, page: ft.Page):
        self.page = page
        self._running = False
        self._save_dir = str(ANDROID_SAVE)
        self._log_ctrls = []

        # 页面设置
        page.title = "无涯图片爬取工具"
        page.padding = 12
        page.window.width = 400
        page.window.height = 720
        page.scroll = ft.ScrollMode.ADAPTIVE
        page.debug = False
        page.show_semantics_debugger = False

        self._build_ui()
        page.update()

    def _build_ui(self):
        page = self.page
        page.controls.clear()

        # ── 标题 ──
        page.add(
            ft.Container(
                content=ft.Column([
                    ft.Text("无涯图片爬取工具", size=24, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.BLUE_400, text_align=ft.TextAlign.CENTER),
                    ft.Text("QQ: 1246792122", size=12,
                            color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER),
                ], spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                margin=ft.Margin(top=12, bottom=8, left=0, right=0),
            )
        )

        # ── 设置卡片 ──
        self.keyword_field = ft.TextField(
            label="搜索关键词", hint_text="输入关键词...",
            border=ft.InputBorder.OUTLINE, dense=True,
        )
        self.count_field = ft.TextField(
            label="下载数量", hint_text="默认10张, 1-200",
            border=ft.InputBorder.OUTLINE, dense=True,
            keyboard_type=ft.KeyboardType.NUMBER,
            value="10",
        )
        self.path_text = ft.Text(
            f"保存位置: {self._save_dir}",
            size=12, color=ft.Colors.GREY_500,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.browse_btn = ft.FilledButton(
            content=ft.Text("浏览...", size=12),
            on_click=self._browse_folder,
        )

        page.add(
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        self.keyword_field,
                        self.count_field,
                        ft.Row([
                            self.path_text,
                            self.browse_btn,
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ], spacing=10),
                    padding=12,
                ),
                elevation=4,
            )
        )

        # ── 下载按钮 ──
        self.start_btn_text = ft.Text("开 始 下 载", size=16)
        self.start_btn = ft.FilledButton(
            content=self.start_btn_text,
            on_click=self._start_download,
        )
        page.add(ft.Container(self.start_btn, margin=ft.Margin(top=8, bottom=8, left=0, right=0)))

        # ── 进度 ──
        self.progress_bar = ft.ProgressBar(value=0, width=400)
        self.progress_text = ft.Text("等待开始...", size=12, color=ft.Colors.GREY_500)
        page.add(
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        self.progress_bar,
                        self.progress_text,
                    ], spacing=6),
                    padding=12,
                ),
                elevation=4,
            )
        )

        # ── 日志 ──
        self.log_column = ft.Column(spacing=1)
        page.add(
            ft.Card(
                content=ft.Container(
                    content=ft.Column([
                        ft.Text("运行日志", size=14, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.BLUE_400),
                        ft.Divider(height=1),
                        ft.ListView(
                            controls=[self.log_column],
                            height=200,
                            auto_scroll=True,
                        ),
                    ], spacing=4),
                    padding=12,
                ),
                elevation=4,
                expand=True,
            )
        )

        # ── 状态栏 ──
        self.status_text = ft.Text("✅ 就绪", size=12, color=ft.Colors.GREY_500)
        page.add(ft.Row([self.status_text], alignment=ft.MainAxisAlignment.START))

    # ── 浏览文件夹 ──────────────────────────

    def _browse_folder(self, e):
        """选择保存目录（Windows 用原生对话框，Android 用手动输入弹窗）"""
        # 先尝试系统原生对话框（Windows/Mac/Linux）
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder = filedialog.askdirectory(
                title="选择保存目录",
                initialdir=self._save_dir,
            )
            root.destroy()
            if folder:
                self._save_dir = folder
                self.path_text.value = f"保存位置: {folder}"
                self.page.update()
            return
        except Exception:
            pass

        # Android 等平台：弹出输入框手动填写路径
        path_input = ft.TextField(
            label="输入保存路径",
            hint_text="/storage/emulated/0/Download/无涯图片",
            value=self._save_dir,
            border=ft.InputBorder.OUTLINE, dense=True,
        )

        def on_ok(ev):
            if path_input.value.strip():
                self._save_dir = path_input.value.strip()
                self.path_text.value = f"保存位置: {self._save_dir}"
                self.page.close(dlg)
                self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("设置保存路径"),
            content=path_input,
            actions=[
                ft.TextButton(content=ft.Text("取消"), on_click=lambda e: self.page.close(dlg)),
                ft.FilledButton(content=ft.Text("确定"), on_click=on_ok),
            ],
        )
        self.page.open(dlg)

    # ── 开始下载 ────────────────────────────

    def _start_download(self, e):
        if self._running:
            return

        keyword = self.keyword_field.value.strip()
        if not keyword:
            self._log("⚠ 请输入搜索关键词")
            self.page.update()
            return

        raw = self.count_field.value.strip()
        if not raw:
            want = DEFAULT_COUNT
        else:
            try:
                want = int(raw)
                if want < 1 or want > 200:
                    self._log("⚠ 数量范围 1-200")
                    self.page.update()
                    return
            except ValueError:
                self._log("⚠ 请输入有效的数字")
                self.page.update()
                return

        sys.modules["_core"]._log_func = self._log_cb

        self._running = True
        self.start_btn_text.value = "下载中..."
        self.start_btn.disabled = True
        self.progress_bar.value = 0
        self.progress_text.value = "🔍 搜索中..."
        self.status_text.value = "🔍 搜索中..."

        self.log_column.controls.clear()
        self._log(f'开始任务: "{keyword}" / {want} 张')
        self._log(f"保存至: {self._save_dir}")
        self._log("-" * 28)
        self.page.update()

        t = threading.Thread(target=self._worker, args=(keyword, want, self._save_dir), daemon=True)
        t.start()

    # ── 后台线程 ─────────────────────────────

    def _worker(self, keyword: str, want: int, save_dir: str):
        try:
            self._ui_log("正在搜索: " + keyword + " ...")
            self._ui_status("🔍 搜索中...")

            _ensure_baidu_cookies()
            pairs = baidu_search(keyword, want, log_cb=self._log_cb)

            if not pairs:
                self._ui_log("❌ 未搜到图片，请检查网络或换关键词。")
                self._ui_reset()
                return

            self._ui_log(f"共获取 {len(pairs)} 对图片地址 (已过滤重复)")

            base_dir = Path(save_dir)
            base_dir.mkdir(parents=True, exist_ok=True)
            existing = list(base_dir.glob(f"{keyword}*"))
            folder = existing[0] if existing else base_dir / keyword
            folder.mkdir(parents=True, exist_ok=True)

            self._ui_log(f"保存至: {folder}")
            self._ui_status("⬇ 下载中...")

            ok = 0; idx = 0
            total_pairs = len(pairs)
            t0 = time.time()

            with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as pool:
                pending = {}
                for _ in range(min(DOWNLOAD_WORKERS, total_pairs)):
                    orig, cdn = pairs[idx]
                    pending[pool.submit(download_one, orig, cdn, folder, idx)] = idx
                    idx += 1

                while pending and ok < want:
                    for fut in as_completed(pending):
                        i, success, msg = fut.result()
                        del pending[fut]
                        if i < total_pairs:
                            DOWNLOADED_URL_SIGS.add(url_sig(pairs[i][0]))
                        if success:
                            ok += 1

                        elapsed = time.time() - t0
                        spd = f"{ok / elapsed:.1f}张/s" if elapsed > 0 else ""
                        self._ui_progress(ok, want, spd)

                        if ok >= want:
                            for f in pending:
                                f.cancel()
                            pending.clear()
                            break

                        need = want - ok
                        slots = max(0, min(DOWNLOAD_WORKERS, need * 4 + 3) - len(pending))
                        for _ in range(slots):
                            if idx >= total_pairs:
                                break
                            orig, cdn = pairs[idx]
                            pending[pool.submit(download_one, orig, cdn, folder, idx)] = idx
                            idx += 1
                        break
                    if not pending:
                        break

            # 重命名
            existing_max = 0
            for f in folder.glob(f"{keyword}_*"):
                m = re.match(rf"{re.escape(keyword)}_(\d+)", f.stem)
                if m:
                    existing_max = max(existing_max, int(m.group(1)))
            tmp_files = sorted(folder.glob("_tmp_*"), key=lambda f: f.stat().st_mtime)
            for f in tmp_files[want:]:
                try: f.unlink()
                except Exception: pass
            for i, f in enumerate(tmp_files[:want], existing_max + 1):
                new_name = folder / f"{keyword}_{i:04d}.jpg"
                try:
                    f.rename(new_name)
                except Exception:
                    alt = folder / f"{keyword}_{i:04d}_{int(time.time()) % 10000:04d}.jpg"
                    try: f.rename(alt)
                    except Exception: pass

            total_files = len(list(folder.glob(f"{keyword}_*.jpg")))
            new_name = f"{keyword}（{total_files}张）"
            new_folder = folder.parent / new_name
            if folder.name != new_name:
                try: folder.rename(new_folder); folder = new_folder
                except Exception: pass

            elapsed = time.time() - t0
            self._ui_done(ok, want, elapsed, str(folder))

        except Exception as ex:
            self._ui_log(f"❌ 异常: {ex}")
            self._ui_reset()

    # ── UI 更新方法（从工作线程安全调用）───────

    def _ui_log(self, text: str):
        self.log_column.controls.append(
            ft.Text(text, size=11, color=ft.Colors.GREY_300)
        )
        self.page.update()

    def _ui_status(self, text: str):
        self.status_text.value = text
        self.page.update()

    def _ui_progress(self, ok: int, want: int, spd: str):
        self.progress_bar.value = ok / want if want > 0 else 0
        self.progress_text.value = f"下载中... [{ok}/{want}] 张 | {spd}"
        self.page.update()

    def _ui_done(self, ok: int, want: int, elapsed: float, folder_path: str):
        self._ui_log("-" * 28)
        self._ui_log(f"✅ 下载完成! {ok}/{want} 张 | {elapsed:.1f}秒")
        self._ui_log(f"📁 {folder_path}")
        if ok < want:
            self._ui_log(f"⚠ 源链接失效, 只下到 {ok} 张。可换关键词重试。")
        self._ui_reset()
        self.status_text.value = f"✅ 完成 ({ok}张)"
        self.page.update()

    def _ui_reset(self):
        self._running = False
        self.start_btn_text.value = "开 始 下 载"
        self.start_btn.disabled = False
        self.page.update()

    # ── 日志回调（核心引擎调用）───────────────

    def _log_cb(self, msg: str, level: str = "info"):
        self._ui_log(msg)

    def _log(self, text: str):
        self._ui_log(text)


# ── 入口 ──────────────────────────────────────
if __name__ == "__main__":
    ft.run(main=lambda page: WuyatuApp(page))
