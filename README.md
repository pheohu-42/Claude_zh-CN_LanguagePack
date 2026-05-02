# Claude Desktop 简体中文语言包（人味版）

为 Claude Desktop (Windows) 的界面语言增加简体中文。


使用 GLM5.1 翻译 + 人工粗校，拒绝机翻味。

<img width="75%" alt="image" src="https://github.com/user-attachments/assets/16c330db-6df9-43ca-a333-61172057ad6e" />

## 前提

- 已安装 [Claude Desktop](https://claude.ai/download)
- Windows 10 / 11，或 macOS
- 自己的 API 端点
- macOS 需要额外安装python

## 快速安装

### Windows

1. 以 git clone 或 zip 的形式下载本仓库
2. 完全关闭 Claude Desktop
3. 双击 `安装中文语言包.bat`。如果界面卡住，可以按几下回车键。
4. 在 管理员权限 弹窗中点击「是」
5. 等待安装完成
6. 打开 Claude ，在左下角设置中切换语言为中文

### macOS（实验性支持）

1. 以 git clone 或 zip 的形式下载本仓库
2. 完全关闭 Claude Desktop
3. 双击 `安装中文语言包.command`
4. 输入 mac 登录密码，允许脚本修改 `/Applications/Claude.app`
5. 等待脚本备份、补丁、重签名并自动拉起 Claude
6. 如果没有自动切换，可在 Claude 设置中选择 `中文（中国）`

如果 `.command` 无法双击运行，请先执行：

```bash
chmod +x ./安装中文语言包.command ./卸载中文语言包.command
```

## 快速卸载

### Windows

1. 完全关闭 Claude Desktop
2. 双击 `卸载中文语言包.bat`
3. 在管理员权限弹窗中点击「是」
4. 等待卸载完成

### macOS

1. 完全关闭 Claude Desktop
2. 双击 `卸载中文语言包.command`
3. 输入 mac 登录密码
4. 脚本会优先恢复最近一次完整备份，并把 `locale` 改回 `en-US`

macOS 不做原地逆向修补。如果没有找到备份，脚本会直接报错，并提示你先恢复或重装官方 Claude.app。

## Cowork 使用教程

### 一、已有官方付费订阅

汉化包不支持官方订阅登录，请使用 3P 模式。

### 二、3P 模式

无付费订阅的账号登录后无法使用 Cowork，需使用 3P 模式并设置自己的 API 端点。

1. 打开 Claude Desktop，不要登录 Claude 账号

2. 打开左上角菜单（三个横杠）：

```text
帮助 → 故障排除 → 启用开发者模式 (Help → Troubleshooting → Enable Developer Mode)
```

如果左上角菜单点不开，可以先点击邮箱输入框，再按 `Tab` 切换选定到菜单按钮并回车。

3. 开启开发者模式后，打开：

```text
开发者 → 配置第三方推理 (Developer → Configure third-party inference)
```

4. 在 connection 页面填写你的第三方接口信息，包括：

```text
Gateway base URL：https://你的 base URL
Gateway API key：你的密钥
Model list：依次添加你想要的模型；如果不添加，Claude 会自动获取
```

<img width="50%" alt="image" src="https://github.com/user-attachments/assets/1e275fdf-1aac-4f4b-a9ad-23b71b49f101" />

注意 base URL 结尾不要带 `/v1`，否则会导致自动获取模型失败，仅显示 legacy 模型。只有本地 API 端点可以使用 `http`，非本地 API 端点要求 `https`。无须勾选 `Skip login-mode chooser`。可按需在 `Telemetry & updates` 标签关闭前两项遥测。

5. 填好后点击：

```text
本地应用 (Apply locally)
```

6. Claude Desktop 会重启，重启后即可正常使用 Cowork。

## 命令行用法

### Windows（PowerShell）

```powershell
# 安装（默认行为，需管理员权限）
powershell -ExecutionPolicy Bypass -File .\LanguagePack.ps1

# 卸载，恢复英文
powershell -ExecutionPolicy Bypass -File .\LanguagePack.ps1 -Uninstall

# 安装/卸载后不自动重启
powershell -ExecutionPolicy Bypass -File .\LanguagePack.ps1 -NoRestart

# 提取英文原文（开发/更新翻译用）
powershell -ExecutionPolicy Bypass -File .\LanguagePack.ps1 -Extract
```

### macOS（Python 3）

```bash
# 安装
sudo /usr/bin/python3 ./LanguagePack.mac.py --user-home "$HOME" --launch

# 卸载，恢复最近一次完整备份
sudo /usr/bin/python3 ./LanguagePack.mac.py --uninstall --user-home "$HOME" --launch

# 干跑：在临时副本里完成补丁与签名校验，但不替换 /Applications/Claude.app
sudo /usr/bin/python3 ./LanguagePack.mac.py --app /Applications/Claude.app --user-home "$HOME" --dry-run

# 提取当前安装版本的英文原文与翻译模板
sudo /usr/bin/python3 ./LanguagePack.mac.py --extract --app /Applications/Claude.app
```

`LanguagePack.mac.py` 支持这些参数：

- `--uninstall`
- `--extract`
- `--app <path>`
- `--user-home <path>`
- `--dry-run`
- `--launch`

## 工作原理

### Windows

安装脚本会做三件事：

1. 写入 `translated-zh-CN/` 下的 3 个 JSON 资源
2. 在 Claude 的 JS 包中补丁语言列表，添加 `"zh-CN"`
3. 将 Claude 的 `config.json` 中 `locale` 设为 `"zh-CN"`

卸载时会删除翻译文件、恢复 JS 备份并重置 `locale` 为 `"en-US"`。

### macOS

安装脚本会做这些事：

1. 定位 `/Applications/Claude.app`，也支持用 `--app` 覆盖
2. 退出 Claude，把整包复制到临时目录后再修改
3. 在 `Contents/Resources/ion-dist/assets/v1/index-*.js` 中补 `zh-CN` 白名单
4. 用一份 mac 专属前端替换表补齐少量不走 i18n 的硬编码文案
5. 读取目标机器当前 `en-US.json`，与仓库里的中文 JSON 按 key 合并生成 `zh-CN.json`
6. 写入桌面壳层 `zh-CN.json`
7. 写入 `statsig/zh-CN.json`，目录不存在时跳过
8. 把 `Localizable.strings` 同时安装到 `zh-CN.lproj` 和 `zh_CN.lproj`
9. 备份原始 app 为 `Claude.backup-before-zh-CN-时间戳.app`
10. 对修改后的 app 从内到外重签名，保留 entitlements，并补 `disable-library-validation`
11. 清理 quarantine，校验签名，再替换回 `/Applications/Claude.app`
12. 将 `~/Library/Application Support/Claude/config.json` 的 `locale` 设为 `zh-CN`

卸载时不做逆向修补，而是直接恢复最近一次完整备份，并把 `locale` 改回 `en-US`。

## 目录结构

```text
├── 安装中文语言包.bat
├── 卸载中文语言包.bat
├── 安装中文语言包.command
├── 卸载中文语言包.command
├── LanguagePack.ps1
├── LanguagePack.mac.py
└── translated-zh-CN/
    ├── ion-dist/zh-CN.json
    ├── desktop-shell/zh-CN.json
    ├── statsig/zh-CN.json
    └── macos/Localizable.strings
```


## 常见问题

**安装后界面没变中文？**

- 确认 Claude Desktop 已重启
- 检查 Claude 设置中的语言是否已切到 `中文(简体)`
- macOS 若脚本提示白名单补丁失败，通常代表 Claude 的前端 JS 结构变了，需要更新脚本

**脚本报权限错误？**

- Windows 会自动请求管理员权限；若被系统拦截请手动允许
- WindowsApps 目录受系统保护，`takeown` + `icacls` 需要管理员权限
- macOS 需要 `sudo`、`codesign`、`xattr`、`osascript`

**Claude 更新后中文消失？**

- Claude 更新会覆盖 resources 目录，需要重新运行安装脚本
- macOS 会在安装时按当前版本的 `en-US.json` 自动补英文兜底；即使新版本新增 key，也不应出现空白文本

**macOS下提示“ Claude.app 已损坏，无法打开......”**
权限问题，可尝试 [解决方案](https://linux.do/t/topic/2044773)

## 开发者说明

- Windows 继续使用 `LanguagePack.ps1 -Extract` 提取 3 类 JSON 原文
- macOS 使用 `LanguagePack.mac.py --extract`，提取4 类资源
- 提取完成后会生成两套目录：
  - `extracted-en-US/`：保存当前已安装 Claude 版本的英文原文
  - `translation-template/`：生成给后续翻译更新用的模板
- Windows 会生成：
  - `extracted-en-US/ion-dist/en-US.json`
  - `extracted-en-US/desktop-shell/en-US.json`
  - `extracted-en-US/statsig/en-US.json`
- macOS 会额外生成：
  - `extracted-en-US/macos/Localizable.strings`
- 翻译时只维护 `translated-zh-CN/` 这一套正式资源：
  - `translated-zh-CN/ion-dist/zh-CN.json`
  - `translated-zh-CN/desktop-shell/zh-CN.json`
  - `translated-zh-CN/statsig/zh-CN.json`
  - `translated-zh-CN/macos/Localizable.strings`
- 更新翻译时，先用上面的提取命令从当前 Claude 版本生成 `extracted-en-US/` 和 `translation-template/`，再回填到 `translated-zh-CN/`

## 许可

仅供个人学习使用。Claude Desktop 是 Anthropic 的产品，本项目与 Anthropic 无关佬友。。

本项目采用 [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-nc-sa/4.0)（CC BY-NC-SA 4.0）授权。

你可以在非商业目的下复制、分发、修改本项目，但必须保留原作者署名、注明修改内容，并以相同协议继续发布衍生版本。

## 感谢

- 简体中文包原型：https://linux.do/t/topic/2040184 by [RICK](https://linux.do/u/lbls888)
- 使用教程：[开启Claude 3P模式与自定义推理端点](https://linux.do/t/topic/2032192) 与 [使用自定义模型映射](https://linux.do/t/topic/2034445)
- [Linux Do 社区](https://linux.do/)：[![](https://ldo.betax.dev/badge/community)](https://linux.do/)。学 AI，上 L 站。
