# data-cli

一个本地使用的多信息源内容 CLI。

## 当前状态

当前实现以 [docs/superpowers/specs/2026-03-12-data-cli-core-redesign-design.md](docs/superpowers/specs/2026-03-12-data-cli-core-redesign-design.md) 为准，核心语义已经切到资源优先命令面：

- core 只保留两层资源模型：`source` / `channel`
- `content` 只是 CLI 命名空间，不是第三层核心资源
- 顶层命令固定为：`source`、`channel`、`content`、`sub`、`group`、`config`、`help`
- `channel search` 和 `content search` 分离
- `content search` 只做远端发现，不落库
- `content update` 只同步已订阅目标，并落库
- `content query` 永远只查本地库
- `content interact` 是显式远端副作用协议，verb 由 source 私有声明
- `--type` 已经移除
- source 通过 `MANIFEST + SOURCE_CLASS` 自动发现，不再手改 core registry

## 当前内置 Source

当前内置 source 及能力矩阵：

| source | channel search | content search | update | query | interact |
| --- | --- | --- | --- | --- | --- |
| `ashare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `bbc` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `hackernews` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `rsshub` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `sina_finance_724` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `wechatarticle` | ❌ | ✅ | ❌ | ❌ | ❌ |

补充说明：

- 当前内置 source 都没有声明 `mode`
- core 已实现 `content.interact` 协议，但当前内置 source 还没有公开 verbs
- `wechatarticle` 是 discovery-only source，只支持远端内容发现
- `rsshub` 依赖可用的 RSSHub 实例地址和路由索引地址

## 环境

- Python `3.12+`
- `uv`

安装依赖：

```bash
uv sync
```

## 启动

推荐直接运行模块入口：

```bash
uv run python -m cli source list
```

当前建议直接使用 `uv run python -m cli ...`。

## 常用命令

### 帮助

```bash
uv run python -m cli help
uv run python -m cli help content search
uv run python -m cli help content update
uv run python -m cli help content query
uv run python -m cli help content interact
uv run python -m cli help ashare
uv run python -m cli help bbc
uv run python -m cli help rsshub
```

### Source 与 Channel

```bash
uv run python -m cli source list
uv run python -m cli source health bbc
uv run python -m cli channel list bbc
uv run python -m cli channel list ashare
```

### 配置

查看 CLI 级配置：

```bash
uv run python -m cli config cli list
uv run python -m cli config cli explain proxy_url
```

查看和设置 source 配置：

```bash
uv run python -m cli config source list rsshub
uv run python -m cli config source explain rsshub base_url
uv run python -m cli config source set rsshub base_url https://rsshub.isrss.com
uv run python -m cli config source unset rsshub base_url
```

检查 source 配置状态：

```bash
uv run python -m cli config source check bbc
uv run python -m cli config source check bbc --for content.search
uv run python -m cli config source check rsshub --for content.update
```

规则：

- `config source check --for` 只接受 canonical action id
- `content.interact` 额外要求 `--verb`
- `config set` 会按 manifest schema 做基础校验，当前至少覆盖 `enum/int/bool/json`

### 分组

```bash
uv run python -m cli group create middle-east
uv run python -m cli group add-source middle-east bbc
uv run python -m cli group add-channel stocks ashare sh600519
uv run python -m cli group show middle-east
uv run python -m cli group list
uv run python -m cli group remove-channel stocks ashare sh600519
uv run python -m cli group delete middle-east
```

### Channel 搜索

```bash
uv run python -m cli channel search --source ashare --query 贵州茅台 --limit 5
uv run python -m cli channel search --source rsshub --query youtube --limit 20
```

规则：

- `channel search` 只做远端 channel 发现
- `channel search` 不落库
- `--source` 和 `--query` 必填
- 默认 `--limit 20`

### Content 搜索

```bash
uv run python -m cli content search --source bbc --query openai --limit 5
uv run python -m cli content search --source hackernews --query openai --limit 20
uv run python -m cli content search --source wechatarticle --query OpenAI --limit 20
```

规则：

- `content search` 只做远端内容发现，不落库
- `--channel` 与 `--query` 至少提供一个
- `--since` 是否支持由 source capability 决定
- 默认 `--limit 20`

### 订阅

```bash
uv run python -m cli sub add --source bbc --channel world
uv run python -m cli sub add --source hackernews --channel top
uv run python -m cli sub add --source ashare --channel sh600519
uv run python -m cli sub list
uv run python -m cli sub list --source bbc
uv run python -m cli sub remove --source bbc --channel world
```

### 更新

```bash
uv run python -m cli content update --source bbc --channel world --limit 10
uv run python -m cli content update --source hackernews --channel top --limit 20
uv run python -m cli content update --source ashare --channel sh600519 --since 20260301
uv run python -m cli content update --source ashare --channel sh600519 --all
uv run python -m cli content update --group stocks
uv run python -m cli content update --group stocks --dry-run
```

规则：

- `content update` 只允许更新已订阅目标
- `--source` 与 `--group` 二选一
- `--channel` 只能和 `--source` 一起用
- `--all` 与 `--since` 互斥
- `--all` 与 `--limit` 互斥
- `--dry-run` 只允许和 `content update --group ...` 一起用
- 默认 `--limit 20`，且按 concrete channel target 生效，不是整批全局总量

### 查询

```bash
uv run python -m cli content query --source bbc --limit 20
uv run python -m cli content query --source hackernews --channel top --limit 20
uv run python -m cli content query --source ashare --channel sh600519 --since 20260301 --limit 60
uv run python -m cli content query --keywords 伊朗 --limit 20
uv run python -m cli content query --group middle-east --keywords 伊朗 --limit 20
```

规则：

- `content query` 永远只查本地数据库
- `--keywords` 只是本地过滤条件
- `--group` 只做本地过滤，不触发远端展开和订阅检查
- `--channel` 必须和 `--source` 一起用
- `--channel` 不能和 `--group` 一起用
- `--all` 与 `--limit` 互斥
- 默认 `--limit 20`

### Interact

命令形态：

```bash
content interact --source <source> --verb <verb> --ref <content_ref> [--ref <content_ref> ...] [verb options...]
```

当前状态：

- core 已实现两段式解析、`content_ref` 校验和审计
- 当前内置 source 还没有公开任何 `interaction_verbs`
- 因此现在可以把它看成“协议已就位，待 source 接线”

`content_ref` 形式：

```text
<source>:content/<percent-encoded-source-id>
```

## 数据文件

默认数据库文件：

```text
data-cli.db
```

当前数据库会保存：

- `channels`
- `subscriptions`
- `groups`
- `group_members`
- `sync_state`
- `health_checks`
- `source_configs`
- `cli_configs`
- `action_audits`
- 各 source 的内容表，例如：
  - `bbc_records`
  - `hackernews_records`
  - `ashare_records`
  - `rsshub_records`
  - `sina_finance_724_records`
  - `wechatarticle_records`

说明：

- 内容记录按 source 物理分表存储，不再使用统一 `content_records`
- `content query` 仍是统一入口，但内部按 source 表查询后再归并
- 这是破坏性重构阶段，旧数据库不做兼容迁移

## 测试

跑全部测试：

```bash
env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u no_proxy -u NO_PROXY .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

### BrowserFetcher 测试

`tests/test_browser_fetcher.py` 是真实集成测试，要求本机有一个开启了 CDP 的 Chrome：

```text
http://127.0.0.1:9222
```

## 当前实现边界

当前版本优先保证协议边界清晰，不做兼容层和兜底。

代码分层：

- `cli/`：参数解析、命令分发、输出格式化
- `core/`：manifest、capability、base class、registry、shared model
- `fetchers/`：HTTP / 浏览器抓取
- `store/`：SQLite 存储、去重、sync state、health、config、audit
- `sources/<name>/source.py`：各 source 自己的站点逻辑

新增 source 的标准路径：

1. 新建 `sources/<name>/source.py`
2. 继承 `BaseSource`
3. 在该文件中声明 `MANIFEST` 与 `SOURCE_CLASS`
4. 不修改中心 registry
