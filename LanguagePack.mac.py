#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_DEFAULT = Path("/Applications/Claude.app")
LANG_CODE = "zh-CN"
LANG_FALLBACK = "en-US"

ROOT = Path(__file__).resolve().parent
TRANSLATED_ROOT = ROOT / "translated-zh-CN"
EXTRACTED_ROOT = ROOT / "extracted-en-US"
TEMPLATE_ROOT = ROOT / "translation-template"

FRONTEND_TRANSLATION = TRANSLATED_ROOT / "ion-dist" / "zh-CN.json"
DESKTOP_TRANSLATION = TRANSLATED_ROOT / "desktop-shell" / "zh-CN.json"
STATSIG_TRANSLATION = TRANSLATED_ROOT / "statsig" / "zh-CN.json"
MACOS_TRANSLATION = TRANSLATED_ROOT / "macos" / "Localizable.strings"

CONTENTS_REL = Path("Contents")
RESOURCES_REL = CONTENTS_REL / "Resources"
FRONTEND_I18N_REL = RESOURCES_REL / "ion-dist" / "i18n"
FRONTEND_ASSETS_REL = RESOURCES_REL / "ion-dist" / "assets" / "v1"
STATSIG_REL = FRONTEND_I18N_REL / "statsig"

CONFIG_REL = Path("Library") / "Application Support" / "Claude" / "config.json"
BACKUP_GLOB = "Claude.backup-before-zh-CN-*.app"
BACKUP_NAME_PREFIX = "Claude.backup-before-zh-CN-"

LOCALIZABLE_SOURCE_CANDIDATES = (
    RESOURCES_REL / "en.lproj" / "Localizable.strings",
    RESOURCES_REL / "Base.lproj" / "Localizable.strings",
    RESOURCES_REL / "en-US.lproj" / "Localizable.strings",
    RESOURCES_REL / "English.lproj" / "Localizable.strings",
)
LOCALIZABLE_TARGET_FOLDERS = ("zh-CN.lproj", "zh_CN.lproj")

LANG_WHITELIST_OLD = '["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID"]'
LANG_WHITELIST_NEW = '["en-US","de-DE","fr-FR","ko-KR","ja-JP","es-419","es-ES","it-IT","hi-IN","pt-BR","id-ID","zh-CN"]'
LANG_WHITELIST_REGEX = re.compile(r'((?:\w+)=\["en-US"(?:,"[^"]+")+)\]')
BACKUP_TIMESTAMP_RE = re.compile(r"^Claude\.backup-before-zh-CN-(\d{8}-\d{6})(?:-\d+)?\.app$")

HARDCODED_FRONTEND_REPLACEMENTS = {
    '"New task"': '"新建任务"',
    '"Projects"': '"项目"',
    '"Scheduled"': '"计划任务"',
    '"Customize"': '"个性化"',
    '"Drag to pin"': '"拖动以固定"',
    '"Drop here"': '"拖到这里"',
    '"Let go"': '"松手"',
    '"Recents"': '"最近使用"',
    '"View all"': '"查看全部"',
}


@dataclass
class MergeStats:
    translated: int
    fallback: int
    extra_ignored: int


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and result.returncode != 0:
        output = result.stdout.strip()
        detail = f"\n{output}" if output else ""
        raise SystemExit(f"Command failed ({' '.join(cmd)}):{detail}")
    return result


def print_step(title: str) -> None:
    print("")
    print(title)


def require_file(path: Path) -> None:
    if not path.is_file():
        raise SystemExit(f"Required file not found: {path}")


def require_directory(path: Path, *, label: str) -> None:
    if not path.is_dir():
        raise SystemExit(f"{label} not found: {path}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def merge_locale_dicts(english_path: Path, translated_path: Path) -> tuple[dict[str, Any], MergeStats]:
    require_file(english_path)
    require_file(translated_path)

    english = load_json(english_path)
    translated = load_json(translated_path)

    if not isinstance(english, dict) or not isinstance(translated, dict):
        raise SystemExit(f"Unsupported locale JSON structure: {english_path}")

    merged: dict[str, Any] = {}
    translated_count = 0
    fallback_count = 0

    for key, english_value in english.items():
        if key in translated:
            merged[key] = translated[key]
            if translated[key] != english_value:
                translated_count += 1
        else:
            merged[key] = english_value
            fallback_count += 1

    extra_ignored = len(set(translated) - set(english))
    return merged, MergeStats(
        translated=translated_count,
        fallback=fallback_count,
        extra_ignored=extra_ignored,
    )


def install_merged_locale(
    *,
    label: str,
    english_path: Path,
    translated_path: Path,
    target_path: Path,
) -> None:
    merged, stats = merge_locale_dicts(english_path, translated_path)
    save_json(target_path, merged)
    print(
        f"  {label}: wrote {target_path} "
        f"({stats.translated} translated, {stats.fallback} fallback, {stats.extra_ignored} old keys ignored)"
    )


def load_entitlements(path: Path) -> dict[str, Any]:
    result = subprocess.run(
        ["codesign", "-d", "--entitlements", ":-", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        data = plistlib.loads(result.stdout)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def chown_if_possible(path: Path) -> None:
    sudo_uid = os.environ.get("SUDO_UID")
    sudo_gid = os.environ.get("SUDO_GID")
    if not sudo_uid or not sudo_gid:
        return
    try:
        os.chown(path, int(sudo_uid), int(sudo_gid))
    except OSError:
        pass


def ensure_translation_assets() -> None:
    for path in (
        FRONTEND_TRANSLATION,
        DESKTOP_TRANSLATION,
        STATSIG_TRANSLATION,
        MACOS_TRANSLATION,
    ):
        require_file(path)


def copy_app_to_workspace(source_app: Path) -> Path:
    require_directory(source_app, label="Claude.app")
    temp_root = Path(tempfile.mkdtemp(prefix="claude-zh-cn-macos."))
    patched_app = temp_root / "Claude.app"
    print(f"  Copying app to temp workspace: {patched_app}")
    run(["ditto", str(source_app), str(patched_app)])
    return patched_app


def quit_claude() -> None:
    run(["osascript", "-e", 'tell application "Claude" to quit'], check=False)
    time.sleep(2)


def patch_language_whitelist(app_path: Path) -> None:
    assets_dir = app_path / FRONTEND_ASSETS_REL
    require_directory(assets_dir, label="Frontend assets directory")

    js_files = sorted(assets_dir.glob("index-*.js"))
    if not js_files:
        raise SystemExit(f"Could not find index-*.js under: {assets_dir}")

    patched_files = 0
    already_registered = 0

    for js_file in js_files:
        content = read_text(js_file)
        if LANG_WHITELIST_NEW in content:
            already_registered += 1
            continue
        if LANG_WHITELIST_OLD in content:
            write_text(js_file, content.replace(LANG_WHITELIST_OLD, LANG_WHITELIST_NEW, 1))
            patched_files += 1
            continue
        patched = LANG_WHITELIST_REGEX.sub(r'\1,"zh-CN"]', content, count=1)
        if patched != content and '"zh-CN"' in patched:
            write_text(js_file, patched)
            patched_files += 1

    if patched_files == 0 and already_registered == 0:
        raise SystemExit("Could not locate Claude's language whitelist. Claude's JS bundle format may have changed.")

    print(f"  Language whitelist: patched {patched_files} file(s), already registered in {already_registered} file(s)")


def patch_hardcoded_frontend_strings(app_path: Path) -> None:
    assets_dir = app_path / FRONTEND_ASSETS_REL
    require_directory(assets_dir, label="Frontend assets directory")

    touched_files = 0
    total_replacements = 0

    for js_file in sorted(assets_dir.glob("*.js")):
        content = read_text(js_file)
        patched = content
        replacements_in_file = 0
        for source, target in HARDCODED_FRONTEND_REPLACEMENTS.items():
            occurrences = patched.count(source)
            if occurrences:
                patched = patched.replace(source, target)
                replacements_in_file += occurrences
        if patched != content:
            write_text(js_file, patched)
            touched_files += 1
            total_replacements += replacements_in_file

    if total_replacements == 0:
        print("  Hardcoded frontend strings: no matches found; continuing")
        return

    print(f"  Hardcoded frontend strings: {total_replacements} replacement(s) across {touched_files} file(s)")


def install_frontend_locale(app_path: Path) -> None:
    install_merged_locale(
        label="ion-dist",
        english_path=app_path / FRONTEND_I18N_REL / f"{LANG_FALLBACK}.json",
        translated_path=FRONTEND_TRANSLATION,
        target_path=app_path / FRONTEND_I18N_REL / f"{LANG_CODE}.json",
    )


def install_desktop_locale(app_path: Path) -> None:
    install_merged_locale(
        label="desktop-shell",
        english_path=app_path / RESOURCES_REL / f"{LANG_FALLBACK}.json",
        translated_path=DESKTOP_TRANSLATION,
        target_path=app_path / RESOURCES_REL / f"{LANG_CODE}.json",
    )


def install_statsig_locale(app_path: Path) -> None:
    statsig_dir = app_path / STATSIG_REL
    if not statsig_dir.is_dir():
        print("  statsig: directory not found, skipped")
        return

    english_path = statsig_dir / f"{LANG_FALLBACK}.json"
    if not english_path.is_file():
        print("  statsig: en-US.json not found, skipped")
        return

    install_merged_locale(
        label="statsig",
        english_path=english_path,
        translated_path=STATSIG_TRANSLATION,
        target_path=statsig_dir / f"{LANG_CODE}.json",
    )


def install_localizable_strings(app_path: Path) -> None:
    require_file(MACOS_TRANSLATION)
    resources_dir = app_path / RESOURCES_REL
    require_directory(resources_dir, label="Resources directory")

    for folder_name in LOCALIZABLE_TARGET_FOLDERS:
        output_path = resources_dir / folder_name / "Localizable.strings"
        copy_file(MACOS_TRANSLATION, output_path)
        print(f"  Localizable: wrote {output_path}")


def find_localizable_strings_source(app_path: Path) -> Path:
    for candidate in LOCALIZABLE_SOURCE_CANDIDATES:
        source = app_path / candidate
        if source.is_file():
            return source

    lproj_matches = sorted((app_path / RESOURCES_REL).glob("*.lproj/Localizable.strings"))
    for source in lproj_matches:
        folder_name = source.parent.name.lower()
        if folder_name.startswith("en") or folder_name == "base.lproj":
            return source

    raise SystemExit("Could not find Localizable.strings in Claude.app")


def sign_path(path: Path, entitlements_dir: Path, *, force_outer_entitlements: bool = False) -> None:
    entitlements = load_entitlements(path)
    if entitlements or force_outer_entitlements:
        entitlements = dict(entitlements)
        entitlements["com.apple.security.cs.disable-library-validation"] = True

    cmd = [
        "codesign",
        "--force",
        "--sign",
        "-",
        "--options",
        "runtime",
        "--preserve-metadata=identifier,flags",
    ]

    if entitlements:
        entitlements_path = entitlements_dir / f"{abs(hash(path.as_posix()))}.plist"
        entitlements_path.write_bytes(plistlib.dumps(entitlements, fmt=plistlib.FMT_XML))
        cmd.extend(["--entitlements", str(entitlements_path)])

    cmd.append(str(path))
    result = run(cmd, check=False)
    if result.returncode != 0:
        detail = result.stdout.strip()
        raise SystemExit(f"Failed to codesign {path}:\n{detail}")


def is_signable_file(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    if path.suffix in {".dylib", ".node", ".so"}:
        return True
    return os.access(path, os.X_OK)


def resign_app(app_path: Path) -> None:
    print("  Re-signing patched app")
    contents_dir = app_path / CONTENTS_REL
    entitlements_dir = Path(tempfile.mkdtemp(prefix="claude-zh-cn-entitlements."))

    bundle_targets: list[Path] = []
    file_targets: list[Path] = []

    for root, dirs, files in os.walk(contents_dir):
        root_path = Path(root)
        for dirname in dirs:
            bundle_path = root_path / dirname
            if bundle_path.suffix in {".app", ".framework"}:
                bundle_targets.append(bundle_path)
        for filename in files:
            file_path = root_path / filename
            if is_signable_file(file_path):
                file_targets.append(file_path)

    for file_path in sorted(file_targets, key=lambda item: len(item.parts), reverse=True):
        sign_path(file_path, entitlements_dir)
    for bundle_path in sorted(bundle_targets, key=lambda item: len(item.parts), reverse=True):
        sign_path(bundle_path, entitlements_dir)
    sign_path(app_path, entitlements_dir, force_outer_entitlements=True)


def clear_quarantine(app_path: Path) -> None:
    run(["xattr", "-dr", "com.apple.quarantine", str(app_path)], check=False)
    print("  Cleared quarantine attribute")


def verify_signature(app_path: Path) -> None:
    result = run(
        ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path)],
        check=False,
    )
    if result.returncode != 0:
        detail = result.stdout.strip()
        raise SystemExit(f"codesign verification failed:\n{detail}")
    print("  codesign verification passed")


def verify_outer_entitlements(app_path: Path, expected_entitlements: dict[str, Any]) -> None:
    signed = load_entitlements(app_path)
    for key, value in expected_entitlements.items():
        if signed.get(key) != value:
            raise SystemExit(f"Outer app entitlement was not preserved: {key}")
    if signed.get("com.apple.security.cs.disable-library-validation") is not True:
        raise SystemExit("Outer app is missing com.apple.security.cs.disable-library-validation after re-signing.")
    print("  Outer app entitlements preserved")


def update_user_locale(user_home: Path, locale: str, *, dry_run: bool) -> None:
    config_path = user_home / CONFIG_REL
    if dry_run:
        print(f"  [dry-run] Would set locale={locale} in {config_path}")
        return

    config_path.parent.mkdir(parents=True, exist_ok=True)
    chown_if_possible(config_path.parent)

    config: dict[str, Any] = {}
    if config_path.is_file():
        try:
            loaded = load_json(config_path)
            if isinstance(loaded, dict):
                config = loaded
        except Exception:
            backup_path = config_path.with_suffix(".json.bak-invalid")
            shutil.copy2(config_path, backup_path)
            chown_if_possible(backup_path)
            print(f"  Existing config was invalid JSON; backed up to {backup_path}")

    config["locale"] = locale
    save_json(config_path, config)
    chown_if_possible(config_path)
    print(f"  Config locale updated: {config_path}")


def make_backup_path(app_path: Path) -> Path:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = app_path.with_name(f"{BACKUP_NAME_PREFIX}{timestamp}.app")
    suffix = 1
    while candidate.exists():
        candidate = app_path.with_name(f"{BACKUP_NAME_PREFIX}{timestamp}-{suffix}.app")
        suffix += 1
    return candidate


def replace_with_patched_app(app_path: Path, patched_app: Path, *, dry_run: bool) -> Path:
    backup_path = make_backup_path(app_path)
    if dry_run:
        print(f"  [dry-run] Would back up {app_path} to {backup_path}")
        print(f"  [dry-run] Patched app kept at: {patched_app}")
        return backup_path

    print(f"  Backing up current app: {backup_path}")
    shutil.move(str(app_path), str(backup_path))
    try:
        print(f"  Installing patched app: {app_path}")
        shutil.move(str(patched_app), str(app_path))
    except Exception:
        if backup_path.exists() and not app_path.exists():
            shutil.move(str(backup_path), str(app_path))
        raise
    return backup_path


def find_latest_backup(app_path: Path) -> Path:
    candidates: list[tuple[str, float, Path]] = []
    for candidate in app_path.parent.glob(BACKUP_GLOB):
        match = BACKUP_TIMESTAMP_RE.match(candidate.name)
        stamp = match.group(1) if match else ""
        candidates.append((stamp, candidate.stat().st_mtime, candidate))

    if not candidates:
        raise SystemExit(
            "No Claude backup was found. Restore or reinstall the official Claude.app first, then try uninstall again."
        )

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def restore_backup(app_path: Path, backup_path: Path, *, dry_run: bool) -> None:
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    displaced_path = app_path.with_name(f"Claude.replaced-by-uninstall-{timestamp}.app")

    if dry_run:
        if app_path.exists():
            print(f"  [dry-run] Would move {app_path} to {displaced_path}")
        print(f"  [dry-run] Would restore {backup_path} to {app_path}")
        return

    moved_current = False
    if app_path.exists():
        shutil.move(str(app_path), str(displaced_path))
        moved_current = True

    try:
        shutil.move(str(backup_path), str(app_path))
    except Exception:
        if moved_current and displaced_path.exists():
            shutil.move(str(displaced_path), str(app_path))
        raise

    if moved_current and displaced_path.exists():
        shutil.rmtree(displaced_path, ignore_errors=True)

    print(f"  Restored backup: {backup_path} -> {app_path}")


def launch_claude(app_path: Path) -> None:
    run(["open", "-a", str(app_path)], check=False)
    print("  Claude launched")


def verify_translation_registration(app_path: Path) -> None:
    zh_frontend = app_path / FRONTEND_I18N_REL / f"{LANG_CODE}.json"
    require_file(zh_frontend)

    values = [value for value in load_json(zh_frontend).values() if isinstance(value, str)]
    chinese_count = sum(1 for value in values if re.search(r"[\u4e00-\u9fff]", value))
    print(f"  Verified zh-CN frontend locale: {chinese_count}/{len(values)} string values contain Chinese")

    js_files = sorted((app_path / FRONTEND_ASSETS_REL).glob("index-*.js"))
    if not js_files:
        raise SystemExit("Could not re-check language whitelist after patching.")

    if not any(LANG_CODE in read_text(js_file) for js_file in js_files):
        raise SystemExit("zh-CN was not found in the patched frontend bundle.")
    print("  Verified language whitelist contains zh-CN")


def install_language_pack(*, app_path: Path, user_home: Path, dry_run: bool, launch: bool) -> None:
    ensure_translation_assets()
    require_directory(app_path, label="Claude.app")

    print_step("=== macOS 安装 Claude 中文语言包 ===")
    print(f"Target app: {app_path}")
    print(f"User home: {user_home}")
    if dry_run:
        print("Mode: dry-run (source app and user config will not be modified)")

    original_entitlements = load_entitlements(app_path)

    print_step("[1/6] 退出 Claude")
    if dry_run:
        print("  Skipped because dry-run does not touch the source app")
    else:
        quit_claude()

    print_step("[2/6] 复制 Claude.app 到临时工作区")
    patched_app = copy_app_to_workspace(app_path)

    print_step("[3/6] 写入 zh-CN 资源并补丁前端")
    patch_language_whitelist(patched_app)
    patch_hardcoded_frontend_strings(patched_app)
    install_frontend_locale(patched_app)
    install_desktop_locale(patched_app)
    install_statsig_locale(patched_app)
    install_localizable_strings(patched_app)

    print_step("[4/6] 重签名并校验")
    resign_app(patched_app)
    clear_quarantine(patched_app)
    verify_signature(patched_app)
    verify_outer_entitlements(patched_app, original_entitlements)
    verify_translation_registration(patched_app)

    print_step("[5/6] 替换应用并写入用户配置")
    backup_path = replace_with_patched_app(app_path, patched_app, dry_run=dry_run)
    update_user_locale(user_home, LANG_CODE, dry_run=dry_run)

    print_step("[6/6] 完成")
    if dry_run:
        print(f"Dry-run output app: {patched_app}")
        print(f"Would keep backup name: {backup_path.name}")
        return

    print(f"Backup kept at: {backup_path}")
    if launch:
        launch_claude(app_path)


def uninstall_language_pack(*, app_path: Path, user_home: Path, dry_run: bool, launch: bool) -> None:
    print_step("=== macOS 卸载 Claude 中文语言包 ===")
    print(f"Target app: {app_path}")
    print(f"User home: {user_home}")
    if dry_run:
        print("Mode: dry-run (app backup and user config will not be modified)")

    backup_path = find_latest_backup(app_path)
    print(f"Latest backup: {backup_path}")

    print_step("[1/4] 退出 Claude")
    if dry_run:
        print("  Skipped because dry-run does not touch the installed app")
    elif app_path.exists():
        quit_claude()
    else:
        print("  Installed Claude.app not found; continuing with backup restore")

    print_step("[2/4] 恢复最近一次完整备份")
    restore_backup(app_path, backup_path, dry_run=dry_run)

    print_step("[3/4] 切回英文配置并校验签名")
    update_user_locale(user_home, LANG_FALLBACK, dry_run=dry_run)
    if not dry_run:
        verify_signature(app_path)

    print_step("[4/4] 完成")
    if not dry_run and launch:
        launch_claude(app_path)


def extract_resource(source: Path, extracted_target: Path, template_target: Path, *, dry_run: bool) -> None:
    require_file(source)
    if dry_run:
        print(f"  [dry-run] Would extract {source} -> {extracted_target}")
        print(f"  [dry-run] Would create template {template_target}")
        return
    copy_file(source, extracted_target)
    copy_file(source, template_target)
    print(f"  Extracted: {source} -> {extracted_target}")
    print(f"  Template: {template_target}")


def extract_english_resources(*, app_path: Path, dry_run: bool) -> None:
    require_directory(app_path, label="Claude.app")

    print_step("=== macOS 提取 Claude 英文资源 ===")
    print(f"Target app: {app_path}")
    if dry_run:
        print("Mode: dry-run (no files will be written)")

    frontend_source = app_path / FRONTEND_I18N_REL / f"{LANG_FALLBACK}.json"
    desktop_source = app_path / RESOURCES_REL / f"{LANG_FALLBACK}.json"
    statsig_source = app_path / STATSIG_REL / f"{LANG_FALLBACK}.json"
    localizable_source = find_localizable_strings_source(app_path)

    print_step("[1/2] 提取 4 类原文资源")
    extract_resource(
        frontend_source,
        EXTRACTED_ROOT / "ion-dist" / f"{LANG_FALLBACK}.json",
        TEMPLATE_ROOT / "ion-dist" / f"{LANG_CODE}.json",
        dry_run=dry_run,
    )
    extract_resource(
        desktop_source,
        EXTRACTED_ROOT / "desktop-shell" / f"{LANG_FALLBACK}.json",
        TEMPLATE_ROOT / "desktop-shell" / f"{LANG_CODE}.json",
        dry_run=dry_run,
    )

    if statsig_source.is_file():
        extract_resource(
            statsig_source,
            EXTRACTED_ROOT / "statsig" / f"{LANG_FALLBACK}.json",
            TEMPLATE_ROOT / "statsig" / f"{LANG_CODE}.json",
            dry_run=dry_run,
        )
    else:
        print(f"  statsig source not found, skipped: {statsig_source}")

    extract_resource(
        localizable_source,
        EXTRACTED_ROOT / "macos" / "Localizable.strings",
        TEMPLATE_ROOT / "macos" / "Localizable.strings",
        dry_run=dry_run,
    )

    print_step("[2/2] 完成")
    if not dry_run:
        print(f"English resources: {EXTRACTED_ROOT}")
        print(f"Translation template: {TEMPLATE_ROOT}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Patch Claude Desktop with zh-CN resources on macOS.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--uninstall", action="store_true", help="Restore the latest full Claude backup and reset locale")
    mode.add_argument("--extract", action="store_true", help="Extract current en-US resources from Claude.app")
    parser.add_argument("--app", type=Path, default=APP_DEFAULT, help="Path to Claude.app")
    parser.add_argument("--user-home", type=Path, default=Path.home(), help="Home directory whose Claude config should be updated")
    parser.add_argument("--dry-run", action="store_true", help="Prepare or validate changes without modifying the source app")
    parser.add_argument("--launch", action="store_true", help="Launch Claude after install or uninstall completes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_path = args.app.expanduser()
    user_home = args.user_home.expanduser()

    if args.extract:
        extract_english_resources(app_path=app_path, dry_run=args.dry_run)
        return 0

    if args.uninstall:
        uninstall_language_pack(
            app_path=app_path,
            user_home=user_home,
            dry_run=args.dry_run,
            launch=args.launch,
        )
        return 0

    install_language_pack(
        app_path=app_path,
        user_home=user_home,
        dry_run=args.dry_run,
        launch=args.launch,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
