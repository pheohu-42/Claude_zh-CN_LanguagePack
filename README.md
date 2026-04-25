# Claude Desktop 简体中文语言包

将 Claude Desktop (Windows) 的界面语言替换为简体中文。

## 前提

- 已安装 [Claude Desktop](https://claude.ai/download)
- 已安装 [Python](https://www.python.org/downloads/) 3.8+

## 快速安装

1. **右键** `LanguagePack.bat` → **以管理员身份运行**
2. 选择「安装中文语言包」
3. 等待安装完成，Claude 会自动重启
4. 在 Claude 设置中确认语言已切换为中文

## 命令行用法

```bash
# 安装（需管理员权限）
python install.py install

# 安装并自动重启 Claude
python install.py install --auto-restart

# 卸载，恢复英文
python install.py uninstall

# 提取英文原文（开发/更新翻译用）
python install.py extract
```

## 工作原理

安装脚本做三件事：

1. **写入翻译文件** — 将 `translated-zh-CN/` 下的 3 个 JSON 复制到 Claude 的 resources 目录
2. **注册 zh-CN 语言** — 在 Claude 的 JS 包中补丁语言列表，添加 `"zh-CN"`
3. **切换配置** — 将 Claude 的 `config.json` 中 `locale` 设为 `"zh-CN"`

卸载时反向操作：删除翻译文件、从备份恢复原始 JS、重置 locale 为 `"en-US"`。

## 目录结构

```
├── LanguagePack.bat                    # 交互式菜单（安装/卸载/提取）
├── install.py                          # 主脚本（install/uninstall/extract）
└── translated-zh-CN/                   # 翻译文件
    ├── ion-dist/zh-CN.json             # 主界面 (12,325 条)
    ├── desktop-shell/zh-CN.json        # 桌面外壳 (355 条)
    └── statsig/zh-CN.json              # 功能开关 (46 条)
```

## 常见问题

**安装后界面没变中文？**
- 确认 Claude Desktop 已重启
- 检查 Claude 设置 → 语言是否显示「中文(简体)」选项
- 如果选项不存在，说明 JS 补丁未生效，可能是 Claude 已更新，需要适配新版

**脚本报权限错误？**
- 必须以管理员身份运行
- WindowsApps 目录受系统保护，`takeown` + `icacls` 需要管理员权限

**Claude 更新后中文消失？**
- Claude 更新会覆盖 resources 目录，需要重新运行安装脚本
- 如果新版 JS 变量名变化，脚本会自动尝试正则匹配

**没有 Python？**
- 从 [python.org](https://www.python.org/downloads/) 下载安装
- 安装时勾选「Add Python to PATH」

## 许可

仅供个人学习使用。Claude Desktop 是 Anthropic 的产品，本项目与 Anthropic 无关。
