# NetEase Music Analytics

一个**本地运行、浏览器查看、以数据可信度为核心**的网易云音乐歌单分析工具。

它同时保留 Codex Skill 和命令行能力，并提供完整的本地 Web 界面：

- 每位歌手的歌曲数量
- 同名歌曲分组
- 时长最长、最短歌曲
- 热度最高、最低歌曲及并列项
- 全部歌曲明细
- 可核验的 CSV 与 Markdown 报告
- 歌手、时长和热度可视化
- 历史报告与两次分析结果比较

![Web interface](docs/dashboard.png)

## 为什么需要这个技能

网易云客户端只会渲染当前可见的少量歌曲。如果通过滚动页面统计，很容易漏掉大量曲目。

本技能直接读取歌单的完整 `trackIds`，再按每批 200 首获取歌曲详情。这样既能快速处理数千首歌曲，也能检查返回数量和缺失项。

## 快速开始

### 本地 Web 应用

需要 Python 3.10 或更高版本。

```powershell
pip install -r requirements.txt
python run.py
```

程序默认只监听 `127.0.0.1:8765`，并自动打开：

```text
http://127.0.0.1:8765
```

输入公开歌单链接后，页面会显示真实的采集进度、完整性状态和统计结果。所有数据都保存在本机 `outputs/web/`。

如果不希望自动打开浏览器：

```powershell
python run.py --no-browser
```

### Codex

把仓库克隆到 Codex 技能目录：

```powershell
git clone https://github.com/selurua223/netease-liked-music-stats.git "$env:USERPROFILE\.codex\skills\netease-liked-music-stats"
```

重新打开 Codex，然后使用：

```text
使用 $netease-liked-music-stats 统计这个公开网易云歌单：[歌单链接或 ID]
```

也可以直接把 `netease-liked-music-stats` 文件夹放入：

```text
%USERPROFILE%\.codex\skills
```

### 命令行

需要 Python 3.10 或更高版本，仅使用标准库，无需安装第三方依赖。

```bash
python scripts/netease_liked_stats.py \
  --playlist-id PLAYLIST_ID \
  --out-dir outputs/PLAYLIST_ID
```

PowerShell：

```powershell
python .\scripts\netease_liked_stats.py `
  --playlist-id PLAYLIST_ID `
  --out-dir .\outputs\PLAYLIST_ID
```

## 输出文件

| 文件 | 内容 |
|---|---|
| `report.md` | 人类可读的统计摘要 |
| `summary.json` | 完整统计结构，包含全部并列极值 |
| `songs.csv` | 全部歌曲及其歌手、专辑、时长、热度 |
| `artist_counts.csv` | 全部歌手的歌曲数量排名 |
| `duplicate_titles.csv` | 全部同名歌曲及其专辑信息 |
| `extrema.csv` | 时长与热度的完整极值清单 |
| `raw_data.json` | 用于核验的原始歌单与歌曲数据 |
| `songs.json` | Web 界面使用的标准化歌曲数据 |
| `metadata.json` | 分析时间、版本、完整性和来源信息 |

## 技术架构

```text
Web 前端
  ↓ HTTP / JSON
FastAPI 本地服务
  ↓
AnalysisService / TaskService
  ↓
collector → normalizer → statistics → integrity
  ↓
JSON / CSV / Markdown 本地报告
```

核心统计代码位于 `src/netease_stats/core/`，Web 和 CLI 使用同一套实现，避免两套结果不一致。

## 本地 API

| 方法 | 路径 | 功能 |
|---|---|---|
| `GET` | `/api/health` | 服务状态 |
| `POST` | `/api/analyze` | 创建分析任务 |
| `GET` | `/api/tasks/{id}` | 查询真实任务进度 |
| `GET` | `/api/reports` | 列出本地报告 |
| `GET` | `/api/reports/{id}` | 获取统计摘要 |
| `GET` | `/api/reports/{id}/songs` | 搜索、筛选和分页歌曲 |
| `GET` | `/api/reports/{id}/export` | 下载 CSV、JSON 或 Markdown |
| `GET` | `/api/reports/{id}/compare/{other_id}` | 比较两次报告 |

交互式 API 文档位于 `http://127.0.0.1:8765/api/docs`。

## 安全边界

- 服务只允许绑定回环地址，默认不开放局域网。
- 不使用网易云账号密码或 Cookie。
- 不上传歌曲、报告或缓存到第三方服务器。
- 报告 ID、导出类型和歌曲查询参数均经过白名单或格式校验。
- 前端不会接受任意本地文件路径。
- ECharts 固定版本随仓库分发，不依赖运行时 CDN。

## 统计口径

- **歌手数量**：每首歌曲中的每位不同署名歌手各计一次，合作歌曲会同时计入多位歌手。
- **同名歌曲**：对歌曲标题进行 Unicode NFC 规范化并去除首尾空格后精确匹配；标题不同的版本不会合并。
- **时长**：使用歌曲详情接口返回的毫秒数并转换为 `分:秒`。
- **热度**：使用网易云歌曲详情接口的 `popularity` 分值，`score` 和 `pop` 作为兼容回退字段。

热度不是播放次数，平台也没有公开其底层计算公式。报告中会保留全部并列歌曲，不把同一分值强行排成单一名次。

## 完整性校验

脚本会检查：

- 歌单声明的数量和实际 `trackIds` 数量
- 每批请求与接口返回的歌曲数量
- 所有请求歌曲是否成功返回
- 是否有缺失歌曲或重复歌曲
- 歌手统计、同名分组和极值的数量关系

网易云旧的歌曲详情接口在请求 500 个 ID 时可能只返回约 201 首而不明确报错，因此本项目固定使用不超过 200 首的批次。

## 限制

- 只支持可公开访问的网易云歌单。
- 依赖网易云当前可访问的公开接口；接口变化可能导致脚本需要更新。
- 不下载音频、不修改歌单，也不使用账号 Cookie 或密码。
- 本项目与网易云音乐或网易公司无官方关联。

## 许可证

[MIT](LICENSE)
