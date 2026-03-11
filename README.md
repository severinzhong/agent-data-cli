# data-cli

一个本地使用的多信息源 CLI。

当前已经接入 3 个 source：

- `bbc`
- `hackernews`
- `ashare`

统一支持这些操作：

- `help`
- `source list`
- `source health <source>`
- `channel list <source>`
- `config list/set/unset/check`
- `group create/delete/list/show/add/remove`
- `search <source> <query>`
- `sub add/remove/list`
- `update <source> [--channel ...]` 或 `update --group ...`
- `query [filters...]`

## 环境

- Python `3.12+`
- `uv`
- 依赖安装：

```bash
uv sync
```

## 启动方式

推荐：

```bash
uv run python -m cli source list
```

也可以直接用虚拟环境里的 Python：

```bash
.venv/bin/python -m cli source list
```

CLI 输出目前使用 `rich` 渲染文本表格。

## 当前 Source

### `bbc`

当前内置 channel：

- `world`
- `business`
- `technology`

### `hackernews`

当前内置 channel：

- `top`
- `new`
- `ask`
- `show`
- `jobs`

### `ashare`

当前支持：

- 搜索股票/指数代码
- 用 `sh600519`、`sz000001` 这种 `channel_key` 查询和订阅
- 历史 `day` 序列数据

当前内置 channel：

- `sh000001`
- `sz399001`
- `sz399006`

当前 `ashare` 的核心数据类型只有：

- `day`

## 常用命令

### 帮助

查看全局帮助：

```bash
uv run python -m cli help
```

查看某个泛用命令帮助：

```bash
uv run python -m cli help query
uv run python -m cli help update
```

查看某个 source 的专用帮助：

```bash
uv run python -m cli help ashare
uv run python -m cli help bbc
uv run python -m cli help hackernews
```

### 查看所有 source

```bash
uv run python -m cli source list
```

### 查看某个 source 的健康状态

```bash
uv run python -m cli source health bbc
uv run python -m cli source health hackernews
uv run python -m cli source health ashare
```

### 查看某个 source 的 channel

```bash
uv run python -m cli channel list bbc
uv run python -m cli channel list hackernews
uv run python -m cli channel list ashare
```

### 配置

查看所有 source 配置：

```bash
uv run python -m cli config list
```

查看某个 source 配置：

```bash
uv run python -m cli config list ashare
uv run python -m cli config list bbc
```

设置配置：

```bash
uv run python -m cli config set bbc proxy_url http://127.0.0.1:7890 --type string
```

删除配置：

```bash
uv run python -m cli config unset bbc proxy_url
```

检查某个 source 的配置声明和当前配置状态：

```bash
uv run python -m cli config check ashare
uv run python -m cli config check bbc
```

说明：

- 所有 source 默认直连
- 只有配置了 `proxy_url` 的 source 才会使用代理
- 当前本地已经为 `bbc` 配置了 `http://127.0.0.1:7890`

### 分组

创建分组：

```bash
uv run python -m cli group create middle-east
```

查看分组列表：

```bash
uv run python -m cli group list
```

向分组添加 source：

```bash
uv run python -m cli group add middle-east source bbc
uv run python -m cli group add middle-east source hackernews
```

向分组添加 channel：

```bash
uv run python -m cli group add stocks channel ashare sh600519
```

查看分组成员：

```bash
uv run python -m cli group show middle-east
```

删除分组成员：

```bash
uv run python -m cli group remove middle-east source bbc
uv run python -m cli group remove stocks channel ashare sh600519
```

### 搜索

```bash
uv run python -m cli search bbc openai --limit 3
uv run python -m cli search hackernews openai --limit 3
uv run python -m cli search ashare 贵州茅台 --limit 5
uv run python -m cli search ashare 中国移动 --limit 5
```

说明：

- `search` 是远端发现动作，不查本地数据库
- 搜索结果可以是不同 kind，例如：
  - `channel`
  - `content`
- `ashare search` 当前返回的是 `channel` 结果
- `ashare search` 会使用专用列显示：`name / channel / url`
- 如果未来某个 source 的搜索结果混合多种 kind，CLI 会按 kind 分段显示

### 订阅

```bash
uv run python -m cli sub add bbc world
uv run python -m cli sub add hackernews top
uv run python -m cli sub add ashare sh600519
```

查看当前订阅：

```bash
uv run python -m cli sub list
uv run python -m cli sub list --source bbc
```

取消订阅：

```bash
uv run python -m cli sub remove bbc world
```

### 更新

更新某个 source 的某个 channel：

```bash
uv run python -m cli update bbc --channel world --limit 5
uv run python -m cli update hackernews --channel top --limit 10
uv run python -m cli update ashare --channel sh600519 --type day --limit 100
uv run python -m cli update ashare --channel sh600519 --type day --since 20260301
uv run python -m cli update ashare --channel sh600519 --all
uv run python -m cli update --group stocks --limit 30
uv run python -m cli update --group stocks --dry-run
```

说明：

- `update` 会把结果写入本地数据库
- 数据库文件默认是当前目录下的 `data-cli.db`
- 内容通过统一 `dedup_key` 去重
- `ashare` 不带 `--type` 时，默认按 `day` 更新
- 当前 `ashare` 只支持 `--type day`
- `--limit` 表示最近 N 条
- `--all` 表示拉取该 type 的全量历史
- `--since YYYYMMDD` 表示从某天开始拉到最新
- `update --group` 会先把 group 展开成具体更新目标
- group 中的 `source` 成员只会展开到该 source 当前已订阅的 channel
- 如果 group 同时包含 `source` 和 `channel`，重复目标会先去重
- `--dry-run` 只展示将要更新的具体目标，不会真的请求远端

### 查询

```bash
uv run python -m cli query --source bbc --limit 3
uv run python -m cli query --source hackernews --channel top --limit 3
uv run python -m cli query --source ashare --channel sh600519 --type day --limit 60
uv run python -m cli query --source ashare --channel sh600519 --type day --since 20260301
uv run python -m cli query --keywords 伊朗 --limit 20
uv run python -m cli query --group middle-east --keywords 伊朗 --limit 20
```

说明：

- `query` 永远只查本地数据库
- `--keywords` 只是过滤条件，不会把 `query` 变成远端搜索
- `ashare query` 现在只从数据库读取 `day` 数据
- 返回顺序是时间从新到旧
- 会使用专用表格列显示：`channel / date / open / close / high / low / volume / amount`
- 如果多 source 查询结果的原生视图 schema 一致，会合并成一张表
- 如果 schema 不一致，会退化成一个按时间排序的通用时间线表

当前 `query/update` 的 typed 参数：

```bash
--type <type>
--limit <n>
--all
--since <YYYYMMDD>
```

## 数据文件

默认数据库文件：

```text
data-cli.db
```

这个文件会保存：

- source 元数据
- channel
- subscriptions
- content records
- sync state
- health checks
- source configs

### source_configs

source 配置统一保存在 SQLite 的 `source_configs` 表中。

每条配置包含：

- `source`
- `key`
- `value`
- `value_type`
- `is_secret`
- `updated_at`

当前建议约定：

- `proxy_url`：通用代理配置项
- 没有配置 `proxy_url`：source 走直连

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

对应测试会验证：

- 能获取 `ws_url`
- 能获取 `user_agent`
- 能打开 `https://example.com`

## 当前实现边界

当前版本是第一版骨架，目标是逻辑清晰，不做复杂兜底。

目前特点：

- source 逻辑都收在各自的 `sources/<name>/source.py`
- 公共协议在 `core/`
- 抓取手段在 `fetchers/`
- 数据库存储在 `store/`
- CLI 入口在 `cli/`

后续扩展新 source 时，正常做法是：

1. 新建 `sources/<name>/source.py`
2. 继承 `BaseSource`
3. 在 `core/registry.py` 注册
