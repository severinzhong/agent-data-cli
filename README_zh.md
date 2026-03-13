# agent-data-cli

[English](./README.md) | [中文](./README_zh.md)

> 让所有数据 AI-Native。
> 把任意数据源 CLI 化。
> AGENT帮你操作，帮你归集数据
> 本项目是一套协议，让数据源能够方便的和AGENT沟通，使用稳定统一的`命令语言`

`agent-data-cli` 是面向 agent 时代的本地信息中心。

过去的大多数数据接口都是为人类设计的，要靠网页、信息流、后台面板和零散 API 去点、去找、去拼。`agent-data-cli` 要做的是把这件事重新组织成一套显式、可脚本化、可本地查询的统一`cli`接口，让 agent 真正能稳定操作数据。

它为 agent 和人类提供统一入口，用来处理：

- 新闻资讯
- 社交媒体内容
- 财经数据
- RSS 订阅源
- 其他可以映射到 `source/channel/content` 模型的内容源

这个仓库本身也是一组可装载的 skills，面向：

- Codex
- Claude Code
- OpenClaw

当这些内置 skills 被加载后，agent 就可以沿着同一套命令面，用一条命令一步步完成 source 发现、更新同步和后续读取。

## 为什么是 agent-data-cli？

- AI-native工具需要稳定的命令面，而不是一堆临时网页路径和站点脚本。
- 多源数据应该表现成一个系统，而不是互不相干的站点适配器集合。
- 发现、同步、本地查询、远端副作用必须有清晰边界。
- Agent 需要一个可以检查、更新、查询、扩展的信息中心，而不是隐式行为堆出来的工具箱。

一句话：`agent-data-cli` 的目标就是让所有数据 AI-Native，并把任意数据源 CLI 化。

## 交给 Agent 安装

把这个仓库地址直接交给你的 agent，你可以直接这样说：

- “从 `https://github.com/severinzhong/agent-data-cli` 安装 `agent-data-cli`，装载内置 skills，然后直接帮我用。”
- “用 `agent-data-cli` 帮我找 source、订阅 channel、同步更新，再读取本地结果。”
- “使用 `agent-data-cli` 里的 source authoring skill，帮我新增一个 source。”

## 从 skills.sh 单独安装这两个 skill

如果你只想安装这两个内置 skill，可以直接执行：

```bash
npx skills add https://github.com/severinzhong/agent-data-cli --skill using-data-cli
npx skills add https://github.com/severinzhong/agent-data-cli --skill authoring-data-cli-source
```

## 语义对齐

`agent-data-cli` 的核心模型只保留两层资源：`source` 和 `channel`。

- `source`：一种具体的数据源实现，也是能力边界，比如一个新闻站点、一个股市数据源，或一个社交媒体平台。
- `channel`：source 内部一个可跟踪目标，可以是一条 feed、一个股票代码、一个 RSSHub 路由。你可以发现 channel、订阅或取消订阅、加入 group，并对已订阅的 channel 执行 `content update`。例如 `bbc` 的 `world`、`ashare` 的 `sh600001`、`rsshub` 的 `/youtube/channel/<id>`。
- `content`：一次远端搜索结果，或一次同步后写入本地的内容记录。你可以用 `content search` 做远端发现，用 `content query` 读取本地库，用 `content update` 把已订阅 channel 的远端内容同步到本地；如果某个 source 以后声明了交互动词，还可以通过 `content interact` 对单条内容执行显式远端操作。


## 当前内置 Source

| Source | Channel Search | Content Search | Update | Query | Interact |
| --- | --- | --- | --- | --- | --- |
| `ashare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `bbc` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `cryptocompare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `hackernews` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `xiaohongshu` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `rsshub` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `sina_finance_724` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `usstock` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `wechatarticle` | ❌ | ✅ | ❌ | ❌ | ❌ |

`xiaohongshu` 首版只把 `user/<user_id>` 建模为正式 channel。给 source 配置完整的 `cookie` 请求头字符串后，可以用 `channel search` 搜用户、用 `content search` 搜笔记、用 `content update` 同步已订阅用户频道，并通过 `content interact` 执行 note 级 `like`、`unlike`、`favorite`、`unfavorite`、`comment`。

感谢 [jackwener/xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli)。

装配 `authoring-data-cli-source` 技能后，对 agent 说把 `https://github.com/jackwener/xiaohongshu-cli` 处理成 source，然后按照 agent 指引操作，完成开发到测试用时 3-4 小时，enjoy～💗

---

# 以下内容由AGNET阅读，人类无需阅读

## 环境要求

- Python `3.12+`
- `uv`

安装依赖：

```bash
uv sync
```

## 代理配置

`proxy_url` 只保留一个字段，但有三种语义：

- 未配置：使用用户当前网络环境
- `http://127.0.0.1:7890`：强制走这个代理
- `direct`：强制直连，并且不继承 CLI 级代理

示例：

```bash
uv run -m adc config cli set proxy_url http://127.0.0.1:7890
uv run -m adc config source set bbc proxy_url direct
uv run -m adc config cli unset proxy_url
```

## 工作方式

对 agent 来说，最短路径就是：

1. 发现 source 或 channel
2. 如果要持续跟踪，就先订阅
3. 把远端数据同步到本地
4. 从本地数据库读取
5. 需要时再执行显式远端交互

统一入口：

```bash
uv run -m adc ...
```

## 命令模型

稳定命令族如下：

```text
source
channel
content
sub
group
config
help
```

语义边界：

- `channel search`：只做远端 channel 发现
- `content search`：只做远端内容发现，不落库
- `content update`：同步已订阅目标并写入本地
- `content query`：只查本地
- `content interact`：只做显式远端副作用

## 最小 CLI 面

保留几个最常用例子就够了：

```bash
uv run -m adc help
uv run -m adc source list
uv run -m adc content search --source bbc --query openai --limit 5
uv run -m adc content update --group stocks --dry-run
uv run -m adc content query --source bbc --limit 10
```

交互命令形态：

```bash
uv run -m adc content interact --source <source> --verb <verb> --ref <content_ref> [--ref <content_ref> ...] [verb options...]
```

## 本地数据

默认数据库文件：

```text
agent-data-cli.db
```

共享存储层会统一保存：

- channels
- subscriptions
- groups
- group members
- sync state
- health checks
- source configs
- cli configs
- action audits
- 各 source 的内容表，例如 `bbc_records`、`rsshub_records`

## 项目结构

```text
cli/        参数解析、命令分发、输出格式化
core/       协议、manifest、registry、共享模型
fetchers/   HTTP / 浏览器抓取
store/      SQLite 持久化、去重、sync state、config、audit
sources/    隔离的 source 实现
skills/     随仓库分发的 agent skills
tests/      单元测试与 CLI 模拟测试
```

当前内置 skills：

- [`using-data-cli`](./skills/using-data-cli/SKILL.md)
- [`authoring-data-cli-source`](./skills/authoring-data-cli-source/SKILL.md)

## 测试

跑全量测试：

```bash
env -u http_proxy -u https_proxy -u all_proxy -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u no_proxy -u NO_PROXY .venv/bin/python -m unittest discover -s tests -p 'test_*.py' -v
```

`tests/test_browser_fetcher.py` 是真实集成测试，要求本机存在一个开启了 CDP 的 Chrome：

```text
http://127.0.0.1:9222
```

## 开发新 Source

新增 source 的标准路径：

1. 新建 `sources/<name>/source.py`
2. 继承 `BaseSource`
3. 声明 `MANIFEST` 和 `SOURCE_CLASS`
4. 把站点逻辑限制在 `sources/<name>/` 内部

如果 source 较复杂，优先在 `sources/<name>/` 下继续拆分本地模块，而不是把所有逻辑堆进一个超大的 `source.py`。
