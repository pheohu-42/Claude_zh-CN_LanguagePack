"""Claude Desktop 简体中文语言包安装/卸载/提取脚本"""

import json
import os
import re
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PACK_DIR = os.path.join(SCRIPT_DIR, "translated-zh-CN")
BACKUP_DIR = os.path.join(os.environ.get("TEMP", "/tmp"), "claude-zh-cn-backup")

# ── 工具函数 ──────────────────────────────────────────────

def find_claude_path():
    """查找 Claude Desktop 安装路径"""
    # 方法1: 通过注册表查 Appx 包
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"Software\Microsoft\Windows\CurrentVersion\Appx\AppxAllUserStore\Deployments",
        )
        i = 0
        while True:
            try:
                name = winreg.EnumKey(key, i)
                i += 1
                if name.startswith("Claude"):
                    # 从包名提取路径
                    parts = name.split("_")
                    if len(parts) >= 2:
                        pkg_family = parts[0] + "_" + parts[1].split(".")[0]
                        path = os.path.join(
                            os.environ.get("ProgramFiles", r"C:\Program Files"),
                            "WindowsApps",
                            name,
                        )
                        if os.path.isdir(path):
                            winreg.CloseKey(key)
                            return path
            except OSError:
                break
        winreg.CloseKey(key)
    except Exception:
        pass

    # 方法2: Get-AppxPackage (需要 PowerShell)
    try:
        result = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             '(Get-AppxPackage -Name Claude).InstallLocation'],
            capture_output=True, text=True, timeout=15
        )
        path = result.stdout.strip()
        if path and os.path.isdir(path):
            return path
    except Exception:
        pass

    # 方法3: 扫描 WindowsApps 目录
    wa = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "WindowsApps")
    if os.path.isdir(wa):
        for entry in sorted(os.scandir(wa), key=lambda e: e.name, reverse=True):
            if entry.name.startswith("Claude") and entry.is_dir():
                return entry.path

    return None


def get_resources_path(claude_path):
    """获取 resources 目录"""
    res = os.path.join(claude_path, "app", "resources")
    if os.path.isdir(res):
        return res
    return None


def grant_write_access(path):
    """获取写入权限 (takeown + icacls)"""
    if not os.path.exists(path):
        return
    try:
        subprocess.run(["takeown", "/f", path, "/a"],
                       capture_output=True, timeout=30)
        identity = os.environ.get("USERNAME", "")
        if identity:
            subprocess.run(
                ["icacls", path, "/grant", f"{identity}:(F)", "/t", "/c"],
                capture_output=True, timeout=30
            )
    except Exception:
        pass


def backup_file(filepath):
    """备份文件到临时目录"""
    if not os.path.isfile(filepath):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    dest = os.path.join(BACKUP_DIR, os.path.basename(filepath))
    shutil.copy2(filepath, dest)


def replace_bytes_in_file(filepath, old_pattern, new_pattern):
    """在文件中替换字节模式"""
    with open(filepath, "rb") as f:
        data = f.read()

    pos = data.find(old_pattern)
    if pos < 0:
        return False

    new_data = data[:pos] + new_pattern + data[pos + len(old_pattern):]
    with open(filepath, "wb") as f:
        f.write(new_data)
    return True


def patch_js_language(res_path):
    """补丁 JS 文件注册 zh-CN 语言"""
    assets_dir = os.path.join(res_path, "ion-dist", "assets", "v1")
    if not os.path.isdir(assets_dir):
        print("  [警告] 未找到 assets 目录，跳过 JS 补丁")
        return False

    js_files = [f for f in os.listdir(assets_dir)
                if f.startswith("index-") and f.endswith(".js")]
    if not js_files:
        print("  [警告] 未找到 index-*.js，跳过 JS 补丁")
        return False

    # 精确匹配模式
    exact_old = b'Mz=["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"]'
    exact_new = b'Mz=["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID","zh-CN"]'

    # 正则匹配模式 (Python re 无引号问题)
    regex_pattern = rb'(\w+=\["en-US"(?:,"[^"]+")+\])'

    patched = False
    for js_name in js_files:
        js_path = os.path.join(assets_dir, js_name)

        # 授权
        grant_write_access(js_path)

        with open(js_path, "rb") as f:
            content = f.read()

        text = content.decode("utf-8", errors="replace")

        # 已注册
        if '"zh-CN"' in text:
            print(f"  已注册: {js_name}")
            patched = True
            continue

        # 备份
        backup_file(js_path)

        # 精确匹配
        if exact_old in content:
            ok = replace_bytes_in_file(js_path, exact_old, exact_new)
            if ok:
                print(f"  JS补丁已应用: {js_name}")
                patched = True
                continue

        # 正则 fallback
        m = re.search(regex_pattern, content)
        if m:
            matched = m.group(0)
            new_array = matched[:-1] + b',"zh-CN"]'
            ok = replace_bytes_in_file(js_path, matched, new_array)
            if ok:
                print(f"  JS补丁已应用(正则): {js_name}")
                patched = True
                continue

        print(f"  [警告] 未匹配到语言列表: {js_name} (Claude 可能已更新)")

    return patched


def unpatch_js_language(res_path):
    """卸载时恢复 JS 语言注册"""
    assets_dir = os.path.join(res_path, "ion-dist", "assets", "v1")
    if not os.path.isdir(assets_dir):
        print("  [警告] 未找到 assets 目录")
        return

    js_files = [f for f in os.listdir(assets_dir)
                if f.startswith("index-") and f.endswith(".js")]

    exact_old = b'Mz=["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID","zh-CN"]'
    exact_new = b'Mz=["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"]'

    regex_pattern = rb'(\w+=\[(?:"[^"]+",)+"zh-CN"\])'

    for js_name in js_files:
        js_path = os.path.join(assets_dir, js_name)
        backup_path = os.path.join(BACKUP_DIR, js_name)

        # 优先从备份恢复
        if os.path.isfile(backup_path):
            grant_write_access(js_path)
            shutil.copy2(backup_path, js_path)
            print(f"  从备份恢复: {js_name}")
            continue

        # 无备份，精确移除
        grant_write_access(js_path)
        with open(js_path, "rb") as f:
            content = f.read()

        if b'"zh-CN"' not in content:
            print(f"  无需恢复: {js_name}")
            continue

        # 精确匹配
        if exact_old in content:
            ok = replace_bytes_in_file(js_path, exact_old, exact_new)
            if ok:
                print(f"  语言注册已恢复: {js_name}")
                continue

        # 正则 fallback
        m = re.search(regex_pattern, content)
        if m:
            matched = m.group(0)
            cleaned = matched.replace(b',"zh-CN"', b'')
            ok = replace_bytes_in_file(js_path, matched, cleaned)
            if ok:
                print(f"  语言注册已恢复(正则): {js_name}")
                continue

        print(f"  [警告] 无法移除 zh-CN: {js_name}")
        print(f"  建议重新安装 Claude Desktop")

    # 清理备份
    if os.path.isdir(BACKUP_DIR):
        shutil.rmtree(BACKUP_DIR, ignore_errors=True)
        print("  备份已清理")


def update_config(locale):
    """更新 Claude config.json"""
    pkg_name = "Claude_pzs8sxrjxfjjc"
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Packages", pkg_name)
    config_paths = [
        os.path.join(base, "LocalCache", "Roaming", "Claude", "config.json"),
        os.path.join(base, "LocalCache", "Roaming", "Claude-3p", "config.json"),
    ]

    for cp in config_paths:
        if os.path.isfile(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    config = json.load(f)
                config["locale"] = locale
                with open(cp, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2, ensure_ascii=False)
                print(f"  {os.path.basename(cp)}")
            except Exception as e:
                print(f"  [警告] 配置更新失败: {os.path.basename(cp)} ({e})")


def restart_claude():
    """重启 Claude Desktop"""
    try:
        subprocess.run(["taskkill", "/f", "/im", "claude.exe"],
                       capture_output=True, timeout=5)
    except Exception:
        pass
    import time
    time.sleep(2)
    claude_path = find_claude_path()
    if claude_path:
        exe = os.path.join(claude_path, "app", "claude.exe")
        if os.path.isfile(exe):
            subprocess.Popen([exe])
            time.sleep(3)
            print("Claude Desktop 已重启")


# ── 命令实现 ──────────────────────────────────────────────

def cmd_install(auto_restart=False):
    print()
    print("=== Claude Desktop 中文语言包安装 ===")
    print()

    # 检查翻译文件
    required = [
        ("ion-dist", os.path.join(PACK_DIR, "ion-dist", "zh-CN.json")),
        ("desktop-shell", os.path.join(PACK_DIR, "desktop-shell", "zh-CN.json")),
        ("statsig", os.path.join(PACK_DIR, "statsig", "zh-CN.json")),
    ]

    # 兼容旧目录
    alt_pack = SCRIPT_DIR
    for name, path in required:
        if not os.path.isfile(path):
            alt = os.path.join(alt_pack, name, "zh-CN.json")
            if os.path.isfile(alt):
                # 更新为旧路径
                idx = required.index((name, path))
                required[idx] = (name, alt)

    for name, path in required:
        if not os.path.isfile(path):
            print(f"[错误] 缺少翻译文件: {path}")
            print("请确保 translated-zh-CN 目录中包含完整的翻译文件。")
            sys.exit(1)
        size_kb = os.path.getsize(path) // 1024
        print(f"  {name}: OK ({size_kb}KB)")

    # 查找 Claude
    print()
    print("[1/5] 查找 Claude Desktop...")
    claude_path = find_claude_path()
    if not claude_path:
        print("[错误] 未检测到 Claude Desktop")
        sys.exit(1)

    res_path = get_resources_path(claude_path)
    if not res_path:
        print(f"[错误] 未找到 resources 目录")
        sys.exit(1)

    print(f"  Claude: {claude_path}")

    # 权限
    print()
    print("[2/5] 获取写入权限...")
    for p in [res_path,
              os.path.join(res_path, "ion-dist"),
              os.path.join(res_path, "ion-dist", "i18n"),
              os.path.join(res_path, "ion-dist", "i18n", "statsig"),
              os.path.join(res_path, "ion-dist", "assets"),
              os.path.join(res_path, "ion-dist", "assets", "v1")]:
        grant_write_access(p)

    # JS 文件也授权
    assets_dir = os.path.join(res_path, "ion-dist", "assets", "v1")
    if os.path.isdir(assets_dir):
        for f in os.listdir(assets_dir):
            if f.startswith("index-") and f.endswith(".js"):
                grant_write_access(os.path.join(assets_dir, f))

    print("  权限处理完成")

    # 安装翻译文件
    print()
    print("[3/5] 安装翻译文件...")

    targets = [
        (required[0][1], os.path.join(res_path, "ion-dist", "i18n", "zh-CN.json")),
        (required[1][1], os.path.join(res_path, "zh-CN.json")),
        (required[2][1], os.path.join(res_path, "ion-dist", "i18n", "statsig", "zh-CN.json")),
    ]

    for src, dst in targets:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  {os.path.relpath(dst, res_path)}")

    # JS 补丁
    print()
    print("[4/5] 注册中文语言...")
    patch_js_language(res_path)

    # 更新配置
    print()
    print("[5/5] 更新配置...")
    update_config("zh-CN")

    print()
    print("=== 语言包安装完成 ===")

    if auto_restart:
        print()
        restart_claude()
    else:
        print()
        print("下一步:")
        print("  1. 重启 Claude Desktop")
        print("  2. 在设置中切换语言为 中文(简体)")
    print()


def cmd_uninstall():
    print()
    print("=== Claude Desktop 中文语言包卸载 ===")
    print()

    print("[1/4] 查找 Claude Desktop...")
    claude_path = find_claude_path()
    if not claude_path:
        print("[错误] 未检测到 Claude Desktop")
        sys.exit(1)

    res_path = get_resources_path(claude_path)
    if not res_path:
        print("[错误] 未找到 resources 目录")
        sys.exit(1)

    print(f"  Claude: {claude_path}")

    print()
    print("[2/4] 删除翻译文件...")
    for f in [
        os.path.join(res_path, "ion-dist", "i18n", "zh-CN.json"),
        os.path.join(res_path, "zh-CN.json"),
        os.path.join(res_path, "ion-dist", "i18n", "statsig", "zh-CN.json"),
    ]:
        if os.path.isfile(f):
            os.remove(f)
    print("  翻译文件已删除")

    print()
    print("[3/4] 恢复语言注册...")
    unpatch_js_language(res_path)

    print()
    print("[4/4] 恢复配置...")
    update_config("en-US")

    print()
    print("=== 语言包卸载完成 ===")
    print("请重启 Claude Desktop 使更改生效")
    print()


def cmd_extract():
    print()
    print("=== Claude Desktop 英文文本提取 ===")
    print()

    print("[1/3] 查找 Claude Desktop...")
    claude_path = find_claude_path()
    if not claude_path:
        print("[错误] 未检测到 Claude Desktop")
        sys.exit(1)

    res_path = get_resources_path(claude_path)
    if not res_path:
        print("[错误] 未找到 resources 目录")
        sys.exit(1)

    print(f"  Claude: {claude_path}")

    en_dir = os.path.join(SCRIPT_DIR, "extracted-en-US")
    tpl_dir = os.path.join(SCRIPT_DIR, "translation-template")

    targets = [
        ("ion-dist", os.path.join(res_path, "ion-dist", "i18n", "en-US.json")),
        ("desktop-shell", os.path.join(res_path, "en-US.json")),
        ("statsig", os.path.join(res_path, "ion-dist", "i18n", "statsig", "en-US.json")),
    ]

    print()
    print("[2/3] 提取 en-US 原文...")
    for name, src in targets:
        if not os.path.isfile(src):
            print(f"  [警告] 未找到: {src}")
            continue

        # 英文输出
        en_out = os.path.join(en_dir, name, "en-US.json")
        os.makedirs(os.path.dirname(en_out), exist_ok=True)
        shutil.copy2(src, en_out)

        # 模板输出
        tpl_out = os.path.join(tpl_dir, name, "zh-CN.json")
        os.makedirs(os.path.dirname(tpl_out), exist_ok=True)
        shutil.copy2(src, tpl_out)

        print(f"  {name}: OK")

    print()
    print("[3/3] 提取完成")
    print()
    print("英文原文目录: extracted-en-US/")
    print("待翻译模板目录: translation-template/")
    print()
    print("翻译说明:")
    print("  1. 翻译 translation-template 目录中的 zh-CN.json")
    print("  2. 只修改 JSON 的 value，不要修改 key")
    print("  3. 不要删除 {count}、{name}、%s、<b>...</b> 等占位符")
    print("  4. 翻译完成后放到 translated-zh-CN 目录")
    print("  5. 然后运行: python install.py install")
    print()


# ── 入口 ──────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Claude Desktop 简体中文语言包")
    parser.add_argument("action", nargs="?", default="install",
                        choices=["install", "uninstall", "extract"],
                        help="操作: install(默认) / uninstall / extract")
    parser.add_argument("--auto-restart", action="store_true",
                        help="安装后自动重启 Claude Desktop")
    args = parser.parse_args()

    if args.action == "install":
        cmd_install(auto_restart=args.auto_restart)
    elif args.action == "uninstall":
        cmd_uninstall()
    elif args.action == "extract":
        cmd_extract()


if __name__ == "__main__":
    main()
