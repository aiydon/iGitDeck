# iGitDeck

内网自用的 Git 仓库镜像与代码洞察看板。自动发现并同步公开仓库，提供代码统计、全文检索、README 预览和只读 clone 服务。

```text
GitHub Trending ──HTTP──▶ 爬虫进程
                             │ POST /api/repos
                             ▼
浏览器 ◀── React SPA ── FastAPI ──▶ SQLite (WAL)
                             │
                             ├──▶ git clone/fetch + worktree
                             ├──▶ scc 代码统计
                             └──▶ git http-backend（只读 smart HTTP）
```

## 快速开始

环境要求：

- Linux / macOS
- Python 3.12（`uv` 会自动准备虚拟环境）
- [bun](https://bun.sh/)（构建前端）
- git
- [scc](https://github.com/boyter/scc) v4.1.0（`make install` 会在系统没有 `scc` 时下载固定版本到 `bin/scc`，并校验 SHA-256）

```bash
make install   # uv sync + bun install + scc + .env + 生成 API 类型 + 构建前端
make run       # uvicorn，监听 .env 中的 IGD_HOST:IGD_PORT
```

打开 `http://127.0.0.1:8000/`。API 文档在 `/docs`。

首次启动会自动创建 `./data`、SQLite 数据库，并启动后台同步调度器。添加第一个仓库后即可看到统计、趋势与 README。

## 功能

- **自动发现**：独立爬虫进程抓取 GitHub Trending，通过 `POST /api/repos` 加入同步列表；也支持页面手动添加（支持 GitLab 多级组，如 `openfoam/core/openfoam`）。
- **镜像同步**：按 `平台/owner/repo` 落盘为 bare 镜像；定时 fetch、更新默认分支、刷新工作区。同仓库互斥，失败按指数退避重试。
- **代码统计**：`scc --format json --percent` 统计代码/注释/空行/文件数，并记录镜像与工作区磁盘占用。
- **语言口径**：所有可视化都统计 scc 报告的全部语言（含 JSON/YAML/TOML/CSV 与 Markdown），不再按编程/标记过滤；总览、详情、列表与语言筛选使用同一集合。百分比按字节加权并归一到 100%，`category` 只用于详情里的「配置 / 文档」标签，不参与过滤。
- **检索**：SQLite FTS5 索引仓库名、owner、描述和 README 纯文本。
- **README 预览**：Markdown 渲染、相对链接与图片重写、后端 HTML 清洗、raw 文件按仓库内路径安全读取。
- **只读 clone**：`git http-backend` 暴露 smart HTTP，`upload-pack` 有并发上限和超时。
- **看板**：全局总览、状态分布、语言分布、仓库筛选/排序/分页；详情默认打开 README，另有“概览 / 结构 / 提交 / 趋势”四个 tab（各仓库同步历史不再进入详情，统一在同步页查看）。
- **最近修改**：详情页展示默认分支最近 30 个提交（作者、时间、文件数、增删行数），页头直接显示最新一条；悬停某条提交可查看完整提交信息与正文。
- **目录树图**：详情页「结构」按镜像提交的 git 文件大小绘制两层矩形树图（类似 WizTree），可在“按大小 / 按文件数”之间切换，悬停显示完整路径、字节数与文件数；过小的目录会合并为「其他 N 项」，避免出现难以辨认的碎块。
- **git 洞察**：默认分支行数趋势、提交活跃度热力图（总览近一年，详情按年并可回溯 4 年）、12 个月代码增删、主要贡献者。
- **同步运维**：独立同步页（全部运行记录、状态筛选、失败重试、一键重试全部失败仓库），整体进度读取服务端状态，刷新页面不会丢失；页头与侧栏都标注距离下次自动同步的时间。
- **侧栏**：仓库状态四态计数、下次同步倒计时、最近到期的 3 个仓库（每个带“距下次同步”的细进度条）、最近同步的 8 个仓库、全局代码行与磁盘占用。
- **实时进度**：克隆/抓取期间按 git 自身进度显示百分比（压缩、接收、解析增量），随后是工作区与统计阶段；进度只存内存，任务结束即清除。
- **工程化**：前后端分离，前端 TypeScript 类型由后端 OpenAPI 生成；所有 SQL 集中在 repository 层；配置只来自 `.env`。

## 使用

### 添加与同步

页面右上角或侧栏的「添加仓库」支持**一行一个地址批量粘贴**（最多 200 条，空行忽略），提交后逐条显示新增、已存在与失败原因。单条地址支持：

- `https://github.com/owner/repo`
- `git@github.com:owner/repo.git`
- `ssh://git@gitlab.com/owner/repo.git`
- `owner/repo`（默认 GitHub）
- GitHub / GitLab / Gitee / Bitbucket 的公开仓库

仓库加入后写入 SQLite，调度器在后台 clone。详情页「立即同步」可手动触发；失败原因会显示在列表、详情和同步历史中。

### 检索与筛选

列表页支持：

- FTS5 全文检索：仓库名、owner、描述、README 纯文本
- 筛选：平台、scc 语言、状态、来源（手动 / 趋势）
- 排序：添加时间、最后同步、最后提交、代码量、磁盘占用、仓库名
- 分页与 URL 状态同步（筛选条件可直接分享）

### Clone

已完成同步的仓库可通过只读 smart HTTP 克隆：

```bash
git clone http://<host>:8000/git/github/owner/repo.git
```

不提供 `receive-pack`，也不支持私有仓库或鉴权，符合内网信任模型。

### Trending 爬虫

爬虫是独立进程，只通过 HTTP 调用主进程，不直接访问数据库：

```bash
make crawler                 # 常驻循环，按 IGD_CRAWLER_INTERVAL_MINUTES 抓取
make crawl-once              # 单次抓取并提交
uv run python -m igitdeck.crawler --once --dry-run   # 只打印发现结果
```

`IGD_CRAWLER_LANGUAGES=python,rust` 可抓取指定语言；空值表示全语言。`IGD_CRAWLER_SINCE` 支持 `daily`、`weekly`、`monthly`。

### 导入某个 GitHub 用户 / 组织的全部仓库

```bash
make import-user GITHUB_USER=aiydon
```

等价于 `uv run python -m igitdeck.crawler.github_user aiydon`，通过 GitHub 公开 API
分页列出该用户的公开仓库，再逐个提交到 `POST /api/repos`（来源记为手动）：

- 默认跳过 fork 与空仓库，`--include-forks` 可包含 fork
- `--limit 20` 限制导入数量，`--dry-run` 只打印不提交
- 大量仓库请留意 GitHub 未认证 API 的速率限制（60 次/小时，每页 100 个仓库）

```bash
uv run python -m igitdeck.crawler.github_user aiydon --dry-run --limit 20
```

cron 示例：

```cron
17 6 * * * cd /srv/iGitDeck && /usr/local/bin/uv run python -m igitdeck.crawler --once >> /var/log/igiddeck-crawler.log 2>&1
```

## 架构

### 分层与依赖方向

```text
config → models → repositories → services → api
              ↘ paths / git / clock（基础设施）
crawler → config / models（仅 HTTP 契约，不依赖业务服务）
```

- **配置**：`config.py` 从单一 `.env` 构造不可变的 `Settings`，不读 YAML/TOML。
- **模型**：`models/` 只放 Pydantic v2 领域与 API 契约；没有 ORM、没有 dataclass 数据模型。
- **数据访问**：`repositories/` 集中全部查询 SQL；`db/schema.py` 是唯一 DDL 来源。
- **业务服务**：`services/` 组织用例；不读环境变量，依赖通过构造函数注入。
- **HTTP 层**：`api/routes/` 仅做参数/响应转换与依赖注入，不写 SQL 或业务规则。
- **组合根**：`main.py` 负责装配容器、生命周期、SPA 静态文件和 uvicorn 入口。

### 目录

```text
src/igitdeck/
  config.py              # .env → Settings（32 项配置）
  urls.py                # clone / raw URL 形状
  paths.py               # 数据目录布局 + 路径越界防护
  clock.py               # SQLite 时间戳转换
  search.py              # FTS5 查询构造 + 命中片段解析
  git.py                 # 所有 git 子进程（统一 timeout）
  models/                # Pydantic 契约：仓库、快照、同步、看板
  db/                    # sqlite3 连接、WAL、FTS5 schema、原子迁移
  repositories/          # repos / snapshots / runs / trends 的 SQL + 共享片段
  services/
    sync.py              # clone → fetch → worktree → scc → README → 快照
    coordinator.py       # 并发上限 + 同仓库互斥
    scheduler.py         # 到期选择与批次提交
    policy.py            # 定时/失败重试退避（纯函数）
    stats_collector.py   # scc 调用与语言归一化
    trends.py            # 从 git 提交历史重建行数趋势
    readme.py            # README 发现、渲染、链接重写、清洗
    catalog.py           # 添加/列表/详情/筛选/删除
    dashboard.py         # 全局聚合
    files.py             # raw 文件安全解析
    git_http.py          # git http-backend 流式响应
    metadata.py          # 可选 GitHub 描述补全
    policy.py            # 到期时间：间隔 + 失败退避（纯逻辑）
    progress.py          # 内存中的同步进度（不落库）
    history.py           # 默认分支最近提交与增删统计
    tree.py              # 目录体积树（git blob 大小）
    trends.py            # 从 git 提交历史重建行数/活跃度/增删/贡献者
    container.py         # 显式依赖装配
  api/                   # FastAPI 路由与错误映射
  crawler/               # GitHub Trending 解析 + HTTP 提交
  main.py                # app factory / lifespan / SPA
  openapi.py             # 导出前端类型契约
  maintenance.py         # 运维 CLI（仓库删除），不暴露 HTTP
frontend/
  src/api/schema.d.ts    # 由 `make types` 从 OpenAPI 生成（不手写）
  src/pages/             # 总览 / 仓库列表 / 仓库详情 / 同步记录（仅做编排）
  src/components/        # 通用组件；repo/ 下为筛选、表格、热力图、贡献者与详情面板
  src/lib/               # 查询状态、图表配置、格式化、Hooks
  src/styles/            # tokens / base / layout / components / pages
tests/                   # 单元 + API + 真实 git HTTP clone 集成测试
scripts/install_scc.py   # 固定版本 scc 下载与校验
.githooks/commit-msg     # 可选提交规范 hook
```

### 数据与落盘

```text
data/
  igiddeck.db                 # SQLite（WAL）+ FTS5
  repos/<platform>/<owner>/<repo>.git
  worktrees/<platform>/<owner>/<repo>/
```

- 仓库列表的事实来源是 SQLite，不是配置文件。
- 统计快照、同步运行日志都在数据库中；磁盘占用与派生字段实时计算。
- 进程日志写入 `<IGD_DATA_DIR>/logs/`（Web 为 `igideck.log`，爬虫与运维命令各用独立文件），超过 `IGD_LOG_MAX_BYTES` 后压缩为带时间戳的 `.gz`，仅保留最近 `IGD_LOG_BACKUPS` 份。
- bare 镜像用于对外 clone；独立 worktree 用于 scc、README 与 raw 文件，两者共享对象库。
- 所有从 HTTP 参数拼出的路径都会 `resolve()` 后校验仍在仓库根内。

### 核心表

| 表 | 用途 |
|---|---|
| `repos` | 仓库身份、状态、描述、README 索引文本、分支、最后同步/提交、失败次数 |
| `repo_snapshots` | 每个仓库仅保留当前提交的代码/注释/空行/文件数/磁盘与各语言字节数 |
| `repo_trends` | 默认分支 git 洞察：行数历史（最多 120 点）、逐日活跃度（约 4 年）、12 月增删、Top 5 贡献者、跳过原因 |
| `sync_runs` | 最近 50 次同步的开始/结束、触发方式、成功失败、commit、消息 |

同步进度不落库：它是任务运行中的瞬时状态，进程重启后由下一次同步重新建立。
| `repos_fts` | FTS5 external-content 表，触发器同步 owner/name/描述/README |

### Web 进程

`create_app()` 是唯一组合根。启动时：

1. 创建数据目录、执行 schema 迁移；
2. 把上次进程中断的 `syncing` 状态恢复为 `pending`，中断的同步记录标记失败；
3. `IGD_AUTO_SYNC=true` 时启动调度器；
4. 挂载 API、OpenAPI、只读 smart HTTP、React SPA 与 `/assets` 静态资源。

## 配置

所有配置集中在 `.env`，完整清单和默认值见 [`.env.example`](.env.example)。常用项：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `IGD_HOST` / `IGD_PORT` | `0.0.0.0` / `8000` | Web 监听地址 |
| `IGD_DATA_DIR` | `./data` | SQLite、镜像与工作区根目录 |
| `IGD_AUTO_SYNC` | `true` | 启动调度器并立即同步新仓库 |
| `IGD_SYNC_CONCURRENCY` | `4` | 同时同步的仓库数上限 |
| `IGD_SYNC_INTERVAL_MINUTES` | `60` | 就绪仓库刷新周期 |
| `IGD_SYNC_RETRY_BASE_MINUTES` / `_MAX_MINUTES` | `5` / `120` | 失败重试指数退避与上限 |
| `IGD_GIT_TIMEOUT_SECONDS` | `3600` | 单条 git 命令硬上限 |
| `IGD_GIT_IDLE_TIMEOUT_SECONDS` | `300` | 流式 clone/fetch 无进展多久后中止；只要持续有传输进度，大仓库可以一直跑到完成 |
| `IGD_GIT_HTTP_CONCURRENCY` | `4` | upload-pack 并发上限 |
| `IGD_GIT_HTTP_TIMEOUT_SECONDS` | `1800` | upload-pack 超时 |
| `IGD_GIT_HTTP_MAX_REQUEST_BYTES` | `8388608` | upload-pack 请求体（含解压后）上限，超出返回 413 |
| `IGD_SCC_BINARY` / `IGD_SCC_TIMEOUT_SECONDS` | `scc` / `600` | scc 路径与超时 |
| `IGD_GIT_INSIGHTS_MAX_COMMITS` | `100000` | 超过该提交数时只扫描最近 N 个提交，趋势图截断并在页面标注 |
| `IGD_LOG_MAX_BYTES` / `IGD_LOG_BACKUPS` | `10485760` / `5` | 单个日志文件上限与保留的压缩备份数 |
| `IGD_FETCH_METADATA` | `true` | 手动添加时通过 GitHub API 补全描述（失败不影响添加） |
| `IGD_CRAWLER_API_BASE_URL` | `http://127.0.0.1:8000` | 爬虫调用主进程的地址 |
| `IGD_CRAWLER_LANGUAGES` / `IGD_CRAWLER_SINCE` | 空 / `daily` | Trending 语言与时间范围 |

环境变量优先于 `.env`。`make install` 在 `.env` 不存在时会复制 `.env.example`。

## HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/overview` | 总览聚合（含全局提交活跃度） |
| `GET` | `/api/filters` | 平台/语言/状态/来源 facets |
| `GET` | `/api/status` | 仓库状态计数、下次同步时间、最近同步仓库与全局统计 |
| `GET` | `/api/syncs` | 全局同步记录（按状态筛选、分页） |
| `POST` | `/api/syncs/retry-failed` | 排队重试所有失败仓库，返回入队数量与仓库 ID |
| `GET` | `/api/syncs/progress` | 当前运行中同步的实时进度（内存态，含仓库名，刷新后仍可读取） |
| `GET` | `/api/repos` | 列表、FTS 搜索、筛选、排序、分页 |
| `POST` | `/api/repos` | 添加仓库（`url`, 可选 `source`, `description`） |
| `POST` | `/api/repos/batch` | 批量添加（`urls` 数组，最多 200 条），逐条返回新增/已存在/失败 |
| `GET` | `/api/repos/{id}` | 详情：最新统计、README、趋势、活跃度、最近提交 |
| `GET` | `/api/repos/{id}/tree` | 目录体积树（按镜像提交的 git blob 大小，最多两层） |
| `POST` | `/api/repos/{id}/sync` | 手动同步（202，重复触发返回 `queued=false`） |
| `GET` | `/api/repos/{id}/raw/{path}` | 工作区内 raw 文件（README 图片/链接） |
| `GET` | `/api/health` | 健康检查 |
| `GET/POST` | `/git/{platform}/{owner}/{repo}/info/refs`、`/git-upload-pack` | 只读 smart HTTP |

仓库删除**不提供 HTTP 接口**（内网无鉴权，任何访问者都能触发），只能由运维在主机上执行：

```bash
make repo-remove REPO_ID=12          # 删除数据库记录、镜像与工作区
make repo-remove REPO_ID=12 FORCE=1  # 正在同步时强制删除
uv run python -m igitdeck.maintenance remove 12
```

完整契约由 FastAPI 生成：`/docs`、`/openapi.json`。前端类型通过

```bash
make types   # 导出 OpenAPI → frontend/openapi.json → src/api/schema.d.ts
```

从后端单一事实来源生成，不在前端重复维护接口类型。

## 开发

```bash
make test        # 后端测试（含真实 git smart HTTP clone）
make lint        # ruff + 前端 tsc
make format      # ruff format/fix
make typecheck   # 仅前端类型检查
make build       # 重新生成 API 类型并构建前端到 frontend/dist
make types       # 仅重新生成前端 API 类型
make api-dev     # 后端 uvicorn --reload :8000
make web-dev     # Vite :5173，代理 /api 与 /git
make hooks       # 安装可选 commit-msg hook
```

后端测试使用临时目录，不读写 `./data`。前端开发服务器代理到 `127.0.0.1:8000`。

### 提交规范

采用 gitmoji + 英文 type + 中文描述：

```text
:sparkles: feat(api): 增加仓库同步接口
🐛 fix(sync): 修复默认分支变化后的 worktree 更新
```

`make hooks` 会设置 `core.hooksPath=.githooks`，启用可选校验。该 hook 允许 `Merge`、`Revert` 与 fixup 提交。

## 设计取舍

- **内网信任模型**：不做用户、权限、token、限流；只读 clone 仍限制为 `upload-pack`。破坏性操作（删除仓库）只保留运维 CLI，不出现在 Web UI 与 API。
- **SQLite 足够**：单进程写、WAL 并发读，避免引入额外组件；repository 层集中 SQL。
- **派生值不落库**：总代码量、语言百分比、状态计数和筛选 facets 均从最新快照实时聚合；只有昂贵的统计快照与同步日志持久化。
- **git 是趋势的事实来源**：`repo_trends` 由默认分支的 `git log --numstat` 生成，不随同步频率漂移；`repo_snapshots` 只保留当前提交的一份统计，趋势不再依赖快照历史。
- **按需补算**：升级或首次访问时，若当前提交尚无趋势（或旧版本只存了行数趋势），详情请求在线程池中按镜像补齐并落库；启动时也会在后台为缺失数据的已就绪仓库补算，避免首个请求等待长历史 git log。
- **导航按任务分组**：总览 / 仓库 / 同步三个入口；仓库与同步带计数徽标，侧栏底部显示同步队列状态并可直接跳到失败或待同步列表。
- **更新时间只看提交**：列表与详情以 git 最后一次提交作为“更新”时间；本地同步时间单独标注为“本地镜像”。
- **提交级一致性**：`repos.commit_sha` 记录已镜像的提交，统计快照与趋势仅在 commit 匹配时展示；同步记录按仓库保留最近 50 条。
- **scc 单一事实来源**：语言名称、行数与字节数直接来自 scc v4 JSON；占比由本系统按字节统一计算，`RepoStats.from_languages` 是唯一的汇总入口，前后端不维护第二套归一化。
- **显式依赖**：服务通过构造函数注入，容器只在 `main.py` 装配；爬虫不 import 业务层。
- **内容边界**：README 经 bleach 清洗；raw 文件响应带 `CSP sandbox` / `nosniff` 且拒绝 `.git` 指针；smart HTTP 请求体有硬上限，clone 权限仅为 `upload-pack`。
- **轮询克制**：列表/详情只在存在同步中仓库且标签页可见时轮询（先 4s，1 分钟后降到 10s），标签页隐藏即停止，避免长 clone 期间刷满访问日志。
- **状态兜底**：调度器每轮回收停留超过“两次 git 超时 + scc 超时”的 `syncing` 行并标记失败，线程意外消失也不会永久卡住轮询与重试。
- **无容器**：uvicorn 主进程 + 独立爬虫进程；Makefile 是唯一构建入口。

## 已知限制

- 仅公开仓库；不支持私有仓库、鉴权、多用户、Webhook、代码内容全文检索。
- GitLab 子组仓库（路径超过 `group/repo` 两段）暂不支持。
- README 仅支持 Markdown 渲染；`.rst` / `.txt` 以纯文本显示。外部图片依赖出网访问。
- scc 解析按 v4 JSON 输出编写；如需其他版本，请设置 `IGD_SCC_BINARY` 并确认输出字段。
- 行数趋势统计的是 git 跟踪的文本行（含文档、配置），与 scc 代码行口径不同；提交数超过 `IGD_GIT_INSIGHTS_MAX_COMMITS`（默认 10 万）时只扫描最近 N 个提交，趋势页会标注截断，并用 HEAD 行数锚定绝对数值。
- 提交活跃度统计全部提交（含 merge）：总览只展示近一年（无年份切换），详情保留最近 4 个日历年并可切换；详情的每年日历固定为 53×7，无提交的日期留白，切换年份只改变标签与颜色。行数趋势与增删按非 merge 提交的 diff 计算，末点以镜像 HEAD 补齐。
- 超大仓库（GB 级）首次同步可达数小时，期间列表页处于“同步中”，属预期。首次同步先抓默认分支，再补全其余引用：中断后再次同步会复用已完成的引用，不会从头重来；但 git 无法恢复只下载了一半的 pack 文件。传输期间只要持续有进度就不会被超时打断，只有长时间无进展或超过硬上限才会终止。
- 同步失败在界面只显示归类后的中文原因（网络、超时、权限、空间等），完整 git 输出写入日志文件，便于排查但不暴露本机路径。
- 可选功能（提交热力图、Top contributors、文件树、语法高亮、License 检测、RSS 等）未实现。

## License

内部使用项目，未指定开源许可证。
