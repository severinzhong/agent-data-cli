# agent-data-cli

[English](./README.md) | [中文](./README_zh.md)

> 让所有数据 AI-Native。
> 把任意数据源 CLI 化。

`agent-data-cli` 是面向 agent 时代的本地信息中心。

过去的大多数数据接口都是为人类设计的，要靠网页、信息流、后台面板和零散 API 去点、去找、去拼。`agent-data-cli` 要做的是把这件事重新组织成一套显式、可脚本化、可本地查询的统一接口，让 agent 真正能稳定操作数据。

它为 agent 和人类提供统一入口，用来处理：

- 新闻资讯
- 社交媒体内容
- 财经数据
- RSS 订阅源
- 其他可以映射到 `source/channel/content` 模型的内容源

命令入口统一为：

```bash
uv run -m adc ...
```

这个仓库本身也是一组可装载的 skills，面向：

- Codex
- Claude Code
- OpenClaw

当这些内置 skills 被加载后，agent 就可以沿着同一套命令面，用一条命令一步步完成 source 发现、更新同步和后续读取。

## 交给 Agent 安装

把这个仓库地址直接交给你的 agent：

```text
https://github.com/severinzhong/agent-data-cli
```

然后让它：

1. clone 仓库
2. 执行 `uv sync`
3. 装载仓库内置 skills
4. 用 `agent-data-cli` 做 source 发现、更新同步和本地读取

你可以直接这样说：

- “从 `https://github.com/severinzhong/agent-data-cli` 安装 `agent-data-cli`，装载内置 skills，然后直接帮我用。”
- “用 `agent-data-cli` 帮我找 source、订阅 channel、同步更新，再读取本地结果。”
- “使用 `agent-data-cli` 里的 source authoring skill，帮我新增一个 source。”

## 为什么是 agent-data-cli？

- AI-native 工具需要稳定的命令面，而不是一堆临时网页路径和站点脚本。
- 多源数据应该表现成一个系统，而不是互不相干的站点适配器集合。
- 发现、同步、本地查询、远端副作用必须有清晰边界。
- Agent 需要一个可以检查、更新、查询、扩展的信息中心，而不是隐式行为堆出来的工具箱。

一句话：`agent-data-cli` 的目标就是让所有数据 AI-Native，并把任意数据源 CLI 化。

## 当前状态

当前实现以这份重构设计为准：

- [data-cli 核心重构设计](./docs/superpowers/specs/2026-03-12-data-cli-core-redesign-design.md)

项目已经切到资源优先命令面：

- 核心模型只保留两层资源：`source` 和 `channel`
- `content` 是 CLI 命名空间，不是第三层核心资源
- 顶层命令固定为 `source`、`channel`、`content`、`sub`、`group`、`config`、`help`
- `channel search` 和 `content search` 分离
- `content search` 只做远端发现，不落库
- `content update` 是唯一会远端同步并写入本地的入口
- `content query` 永远只查本地数据库
- `content interact` 是显式远端副作用协议
- source 通过 `MANIFEST + SOURCE_CLASS` 自动发现

## 当前内置 Source

| Source | Channel Search | Content Search | Update | Query | Interact |
| --- | --- | --- | --- | --- | --- |
| `ashare` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `bbc` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `hackernews` | ❌ | ✅ | ✅ | ✅ | ❌ |
| `rsshub` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `sina_finance_724` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `wechatarticle` | ❌ | ✅ | ❌ | ❌ | ❌ |

补充说明：

- 当前内置 source 都没有声明 `mode`
- core 已实现 `content.interact` 协议，但内置 source 还没有公开 verbs
- `wechatarticle` 是 discovery-only source
- `rsshub` 依赖可用的 RSSHub 实例地址和路由索引地址

## 环境要求

- Python `3.12+`
- `uv`

安装依赖：

```bash
uv sync
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
