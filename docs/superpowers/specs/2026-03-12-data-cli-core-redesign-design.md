# data-cli 核心重构设计

- 日期: 2026-03-12
- 状态: 已确认设计，待进入 implementation plan
- 范围: core/cli/source 协议层重构

## 目标

这次重构的目标不是修补现有 CLI，而是重新收紧 core：

- 保留并强化 `source/channel` 两层资源模型
- 去掉 `--type`
- 把命令语义统一到一套长期稳定的资源优先风格
- 让 capability 成为核心协议，而不是零散布尔开关
- 让 source 在自己目录内单点声明协议，不再修改 core registry
- 让 help/config/check 基于同一份声明自动生成，减少重复文本
- 明确 `search / update / query / interact` 的边界
- 保持 source 实现自由，但把 core 约束收紧

项目是单用户 CLI，可以接受破坏性更新，不做兼容迁移层，不做兜底，不做隐式 fallback。

## 已确认决策

- CLI 采用资源优先风格，不采用动作优先风格
- 顶层命令固定为 `source/channel/content/sub/group/config/help`
- `channel search` 与 `content search` 分开
- `search` 永不落库
- `update` 只更新已订阅目标，并落库
- `query` 永远只查本地库
- source 不支持某个 option 时：
  - 当前 mode 下永远无效则 help 不展示
  - 仅因缺配置暂不可执行则 help 展示并标记原因
  - 用户硬传时直接报错
- source 可以声明一个唯一行为选择器 `mode`
- 条件 config 只允许基于 `mode`
- `content interact` 进入核心协议
- `content interact` 的 `verb` 完全由 source 私有定义
- `content interact` 必须显式提供 `--source`

## 非目标

- 不引入第三层核心资源
- 不实现调度器、worker 或任务队列
- 不实现跨 source 组合协议
- 不把平台私有行为标准化为 core 词表
- 不让 source 直接管理 SQLite 或解析 CLI

## 命令面

`content` 是 CLI 命名空间，不是新的核心资源层。架构中的核心资源模型仍然只有 `source/channel` 两层；`content` 表示“围绕已归一化内容记录的一组统一操作入口”。


### 顶层命令

```bash
dc source ...
dc channel ...
dc content ...
dc sub ...
dc group ...
dc config ...
dc help ...
```

### 目标命令形态

```bash
dc source list
dc source health <source>

dc channel list <source>
dc channel search --source <source> --query <query> [--limit <n>] [--jsonl]

dc content search --source <source> [--channel <channel>] [--query <query>] [--since <since>] [--limit <n>] [--jsonl]
dc content update --source <source> [--channel <channel>] [--since <since>] [--limit <n>] [--all]
dc content update --group <group> [--since <since>] [--limit <n>] [--all] [--dry-run]
dc content query [--source <source>] [--channel <channel>] [--group <group>] [--keywords <keywords>] [--since <since>] [--limit <n>] [--all] [--jsonl]

dc content interact --source <source> --verb <verb> --ref <content_ref> [--ref <content_ref> ...] [verb options...]

dc sub add --source <source> --channel <channel> [--name <name>]
dc sub remove --source <source> --channel <channel>
dc sub list [--source <source>]

dc group create <group>
dc group delete <group>
dc group list
dc group show <group>
dc group add-source <group> <source>
dc group add-channel <group> <source> <channel>
dc group remove-source <group> <source>
dc group remove-channel <group> <source> <channel>

dc config cli list
dc config cli set <key> <value>
dc config cli unset <key>
dc config cli explain <key>

dc config source list <source>
dc config source set <source> <key> <value>
dc config source unset <source> <key>
dc config source explain <source> <key>
dc config source check <source>
dc config source check <source> --for content.search
dc config source check <source> --for content.update
dc config source check <source> --for content.interact --verb <verb>

dc help
dc help source
dc help channel search
dc help content search
dc help content update
dc help content interact
dc help <source>
```

## 语义约束

### `channel`

- `channel list` 读取 source 提供的 channel 列表
- `channel search` 只做远端 channel 发现
- `channel search` 不落库

### `content search`

- 只做远端内容发现
- 不落库
- `--channel`、`--query`、`--since`、`--limit` 是否可用，由 source capability 决定
- 不支持的 option 直接报错，不允许静默忽略
- 允许把“未订阅 channel 的临时查看”放在这里解决，不新增临时落库命令

### `content update`

- 只同步已订阅目标
- 会落库
- `content update --source foo` 表示更新 `foo` 下所有已订阅 channel
- `content update --group g` 先展开 group，再校验目标必须已订阅
- 未订阅 channel 执行 update 直接报错
- `--dry-run` 只展示展开目标，不执行远端请求

### `content query`

- 永远只查本地库
- `--keywords` 只是本地过滤条件
- `--since` 只是本地时间过滤条件
- 不会触发远端搜索或远端同步

### `content interact`

- 是远端副作用操作协议
- 永不隐式落库
- 永不隐式触发 update
- 只能显式触发
- 只能对显式 `--ref` 执行
- 第一版批量仅支持显式多 `--ref`
- 同一条命令内所有 `--ref` 必须属于同一 source
- `content_ref` 不要求本地数据库内已有对应记录；远端 search 返回的 ref 也可直接使用

## 核心协议模型

### 核心资源

- `source`
- `channel`
- `content` 不是核心资源，而是 CLI 命名空间与统一内容协议名

### 辅助本地模型

- `subscription`
- `group`
- `config`
- `content record`

### 标准 source action 集

下面这些 action 由 source 实现，manifest 只能声明它们的子集，不能自创新的 source action：

- `source.health`
- `channel.list`
- `channel.search`
- `content.search`
- `content.update`
- `content.interact`

### core 本地命令

下面这些命令由 core/store 执行，不属于 source action：

- `content.query`
- `sub.add`
- `sub.remove`
- `sub.list`

source 只通过 `storage` 与 `query` 相关声明影响它们的行为。

### 标准 option 集

#### core 解析并拥有的 option

- `source`
- `group`
- `jsonl`
- `dry_run`
- `verb`
- `ref`
- `name`

#### 由 manifest capability 决定是否支持的 option

- `channel`
- `query`
- `keywords`
- `since`
- `limit`
- `all`

core 维护统一 option 词表，source 不发明新的通用 option，只声明 source-sensitive option 是否支持以及依赖哪些配置。

### canonical id 规范

- action id 使用点分形式，例如 `content.search`
- 内部 option id 使用 snake_case，例如 `dry_run`
- CLI flag 形式统一由内部 option id 映射为 kebab-case，例如 `dry_run -> --dry-run`
- `config source check --for <action-id>` 只能接受 canonical action id
- 只有 `content.interact` 会在 `--for content.interact` 之外额外要求 `--verb <verb>`
- `config source check --for <action-id>` 支持：`source.health`、`channel.list`、`channel.search`、`content.search`、`content.update`、`content.query`、`content.interact`

## 默认值与时间语义

- `channel search` 默认 `--limit 20`
- `content search` 默认 `--limit 20`
- `content query` 默认 `--limit 20`
- `content update` 默认 `--limit 20`，且这个 limit 作用于每个 concrete channel target，而不是整个批次的全局总量
- `--since` 支持 `YYYYMMDD` 与相对时间 `Nm/Nh/Nd/Nw`
- 相对时间以 CLI 本地时区的当前时间计算
- `YYYYMMDD` 以 CLI 本地时区的自然日零点起算
- core 负责把 `--since` 解析为 timezone-aware UTC `datetime`
- query/source 接口接收的 `since` 都是这个 canonical `datetime | None`
- 未显式提供 `--since/--limit/--all` 时，使用各命令默认 limit，不做隐式全量语义

`content.interact` 的私有参数不属于通用 option 词表，而是 verb schema 的一部分。

## 参数矩阵

### `channel search`

- `--source` 必填
- `--query` 必填
- `--limit` 可选
- `--jsonl` 可选
- 不支持 `--channel`
- 不支持 `--group`

### `content search`

- `--source` 必填
- `--channel` 可选
- `--query` 可选
- `--channel` 与 `--query` 至少提供一个
- `--since` 可选，但是否支持由 source capability 决定
- `--limit` 可选
- `--jsonl` 可选
- 不支持 `--group`
- 不支持 `--all`

### `content update`

- `--source` 与 `--group` 二选一，且必须提供其一
- `--channel` 仅可与 `--source` 组合使用
- `--channel` 出现时表示只更新该单个已订阅 channel
- `--all` 与 `--since` 互斥
- `--all` 与 `--limit` 互斥
- `--limit` 可选
- `--dry-run` 只允许与 `content update --group ...` 组合
- 不支持 `--jsonl`

### `content query`

- `--source`、`--group` 二选一；两者都不提供时表示全库查询
- `--channel` 必须与 `--source` 一起使用
- `--channel` 不能与 `--group` 同时使用
- `--all` 与 `--limit` 互斥
- `--since` 可与 `--limit` 组合
- `--jsonl` 可选
- `--keywords` 可选
- 不做“`--since` 自动等价 `--all`”这类隐式语义

### `content interact`

- `--source` 必填
- `--verb` 必填
- `--ref` 至少一个
- 所有 ref 必须与 `--source` 一致
- ref 只能显式枚举，不支持 `--group`、`--query`、`--all`
- verb 私有参数跟在通用参数之后解析

## 错误矩阵

- `--channel` 缺少 `--source`：直接报错
- `content update` 同时传 `--source` 与 `--group`：直接报错
- `content update --all --since ...`：直接报错
- `content update --all --limit ...`：直接报错
- `content query --channel ... --group ...`：直接报错
- `content search` 同时缺少 `--query` 与 `--channel`：直接报错
- `content interact` refs 跨 source：直接报错
- action/option/verb/param 不支持：直接报错

## `SourceManifest`

每个 source 在 `sources/<name>/source.py` 中声明一个 manifest，作为该 source 的协议真相。

source 模块必须导出：

- `MANIFEST: SourceManifest`
- `SOURCE_CLASS: type[BaseSource]`

### manifest 字段

- `identity`
  - `name`
  - `display_name`
  - `summary`
- `mode`
  - 可选
  - `default`
  - `choices`
  - 每个 mode 的说明
- `config_fields`
  - source 配置字段 schema
- `source_actions`
  - 标准 source action 的能力声明
- `query`
  - core 本地查询所需的 source 特有声明
- `interaction_verbs`
  - `content.interact` 的私有 verb 声明
- `storage`
  - source 存储声明
- `docs`
  - source 专用 help 补充

### 设计原则

- manifest 是协议真相
- `__doc__` 可以作为补充文案来源，但不是协议真相
- help、config check、capability check、parser 裁剪都基于 manifest
- source 的站点抓取、接口调用、浏览器自动化都留在实现层，不进入 manifest 之外的 core 逻辑


### manifest 结构

manifest 的结构在本设计中固定，不留到实现阶段再发明：

```python
@dataclass(slots=True)
class SourceManifest:
    identity: SourceIdentity
    mode: ModeSpec | None
    config_fields: tuple[ConfigFieldSpec, ...]
    source_actions: dict[str, SourceActionSpec]
    query: QuerySpec | None
    interaction_verbs: dict[str, InteractionVerbSpec]
    storage: StorageSpec
    docs: DocsSpec | None = None


@dataclass(slots=True)
class SourceIdentity:
    name: str
    display_name: str
    summary: str


@dataclass(slots=True)
class ModeSpec:
    key: str
    default: str
    choices: tuple[ModeChoice, ...]


@dataclass(slots=True)
class ModeChoice:
    value: str
    summary: str


@dataclass(slots=True)
class ConfigFieldSpec:
    key: str
    type: str
    secret: bool
    description: str
    obtain_hint: str = ""
    example: str = ""
    choices: tuple[str, ...] = ()
    inherits_from_cli: str | None = None
    for_modes: tuple[str, ...] = ()


@dataclass(slots=True)
class SourceActionSpec:
    name: str
    summary: str
    supported_modes: tuple[str, ...] = ()
    options: dict[str, ActionOptionSpec] = field(default_factory=dict)
    config_requirements: tuple[ConfigRequirement, ...] = ()
    result_kinds: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()


@dataclass(slots=True)
class ActionOptionSpec:
    name: str
    supported_modes: tuple[str, ...] = ()
    config_requirements: tuple[ConfigRequirement, ...] = ()
    help_summary: str = ""


@dataclass(slots=True)
class QuerySpec:
    time_field: str | None = "published_at"
    supports_keywords: bool = True
    view_id: str | None = None
    view_fields: tuple[str, ...] = ()


@dataclass(slots=True)
class ConfigRequirement:
    keys: tuple[str, ...]
    for_modes: tuple[str, ...] = ()
    reason: str = ""


@dataclass(slots=True)
class InteractionVerbSpec:
    name: str
    summary: str
    supported_modes: tuple[str, ...] = ()
    params: tuple[InteractionParamSpec, ...] = ()
    config_requirements: tuple[ConfigRequirement, ...] = ()
    examples: tuple[str, ...] = ()


@dataclass(slots=True)
class InteractionParamSpec:
    name: str
    type: str
    required: bool = False
    description: str = ""
    choices: tuple[str, ...] = ()
    multiple: bool = False
    for_modes: tuple[str, ...] = ()


@dataclass(slots=True)
class StorageSpec:
    table_name: str
    required_record_fields: tuple[str, ...]
    unique_key_fields: tuple[str, ...] = ("source", "content_ref")


@dataclass(slots=True)
class DocsSpec:
    notes: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
```

解释：

- `mode.key` 固定为 `mode`
- `supported_modes=()` 表示“不受 mode 限制”
- `for_modes=()` 表示“所有 mode 可见”
- `config_requirements` 只表达“哪些 key 在哪些 mode 下必需”
- 不引入更复杂的条件表达式
- `source_actions` 只包含 source 执行的 action，不包含 `content.query` 与 `sub.*`
- `query` 描述 core 本地查询的 source 特有部分
- `required_record_fields` 至少包含 `source/channel_key/content_ref/title/url/published_at/fetched_at/raw_payload`
- `unique_key_fields` 固定默认值为 `(source, content_ref)`，作为 upsert 与去重键

### 命名约束

- `SourceIdentity.name` 必须匹配 `^[a-z][a-z0-9_]*$`
- source 名不能与顶层命令重名：`source/channel/content/sub/group/config/help`
- `source_actions` 的 dict key 必须等于对应 `name`
- `interaction_verbs` 的 dict key 必须等于对应 `name`
- `ActionOptionSpec.name` 与 `InteractionParamSpec.name` 必须匹配 `^[a-z][a-z0-9-]*$`
- 私有 param 名不能占用保留字：`source/group/channel/query/keywords/since/limit/all/jsonl/dry-run/verb/ref/help/mode/name`

## `mode`

### 作用

`mode` 是 source 唯一行为选择器，用来表达同一个语义 source 在不同运行形态下的行为差异。

例如：

- `wechatarticle.mode = api | cookie | playwright | auto`
- 某些 source 可以没有 `mode`

### 规则

- 一个 source 最多一个 `mode`
- `mode` 必须是 enum
- `mode` 不是手写在 `config_fields` 里的普通字段，而是由 `ModeSpec` 自动生成的隐式 source config 字段
- 条件 config 只允许基于 `mode`
- action / option / verb / verb param 可按 `mode` 裁剪

### 关于 `auto`

允许 source 显式声明 `mode=auto`，但它不是 fallback 机制。

约束：

- `auto` 必须是显式配置值
- source 必须把 `auto` 解析成单一 effective mode
- CLI `config check` 与 help 要能显示当前 effective mode
- 失败时直接失败，不做隐藏的升级/降级链路

### effective mode 解析接口

如果 manifest 声明了 `mode`，则 source 必须实现：

- `resolve_mode() -> str`

规则：

- 返回值必须是 `ModeSpec.choices` 中的一个非 `auto` 值
- 如果当前配置不是 `auto`，`resolve_mode()` 直接返回该显式 mode
- 如果当前配置是 `auto`，`resolve_mode()` 负责选出一个 concrete mode，或直接抛错
- core 在 help、`config source check`、capability 解析、命令执行前都以 `resolve_mode()` 的结果作为 effective mode

## config 模型

### config scope

- `cli`
- `source`

### source config 字段 schema

每个字段只允许声明下面这些属性：

- `key`
- `type`
- `secret`
- `description`
- `obtain_hint`
- `example`
- `choices`
- `inherits_from_cli`
- `for_modes`


### 支持类型

- `string`
- `int`
- `bool`
- `enum`
- `url`
- `path`
- `json`

### 设计原则

- config 字段只描述“这是什么”
- action / verb 依赖负责描述“什么时候需要它”
- 不引入通用规则语言
- 不支持任意布尔表达式
- 不支持 key 之间的复杂互锁关系

### CLI config

CLI config 用同一套 schema 模型定义，但 scope 为 `cli`。

预期字段包括：

- `proxy_url`
- `default_user_agent`
- `browser_profile_dir`
- `browser_ws_endpoint`
- `browser_binary`
- `headless`

### 继承规则

source config 解析优先级固定为：

1. source 显式配置
2. CLI config 继承值
3. source 内置默认值

如果 source 声明了 `mode`，则它的解析优先级是：

1. source 显式配置的 `mode`
2. `ModeSpec.default`

`mode` 不从 CLI config 继承。

## capability 解析

### 两层能力

- `declared capability`
  - source 理论上声明支持什么
- `effective capability`
  - 当前 `mode + config` 下真正可执行什么

CLI、help、参数校验、`config check` 全部基于 `effective capability`。

### source action 能力声明内容

每个 source action 至少声明：

- `summary`
- `supported_modes`
- `options`
- `config_requirements`
- `result_kinds`
- `examples`

### option 级支持

source 需要能表达：

- 某 action 支持哪些 option
- 某 option 在哪些 mode 下支持
- 某 option 是否依赖额外 config

例如：

- `content.search` 支持 `query/channel/limit`
- `content.search --since` 只在 `mode=playwright` 下支持
- `content.update --all` 只在某些 source 下支持


### `effective capability` 与 help 展示规则

- 因 `mode` 不支持而无效的 action / option / verb / param：在当前 help 中隐藏
- 因配置缺失而暂不可执行的 action / option / verb / param：在 help 中展示，但标记 `requires config`
- `config source check` 必须区分：
  - mode 不支持
  - 配置缺失
  - 已可执行

这样用户仍能发现“只差配置即可启用”的能力，但不会看到当前 mode 永远不可能启用的噪音项。

### `content.query` 的 source 声明

`content.query` 由 core/store 执行，但会消费 source manifest 中的：

- `storage.required_record_fields`
- `query.time_field`
- `query.supports_keywords`
- `query.view_id`
- `query.view_fields`

规则：

- 命令默认 `--limit 20` 是全局固定值，source 不能覆盖
- 如果目标 source 的 `query.supports_keywords=False`，传入 `--keywords` 直接报错
- 如果多 source 查询时 `query.view_id` 与 `query.view_fields` 都一致，CLI 可以合并渲染
- 如果 `query.view_id` 或 `query.view_fields` 不一致，CLI 退回通用时间线视图
- 如果 `query.time_field is None`，该 source 不支持 `--since`
- `query.view_fields` 定义该 source-native query 视图输出的最小 row contract

### `content.interact`

`content.interact` 是唯一的内容副作用 action。

它不维护 core 标准 verb 词表。verb 全部由 source 私有定义。

每个 verb 至少声明：

- `name`
- `summary`
- `supported_modes`
- `params`
- `config_requirements`
- `examples`

每个 param 至少声明：

- `name`
- `type`
- `required`
- `description`
- `choices`
- `for_modes`
- `multiple`

`InteractionParamSpec.type` 只允许：

- `string`
- `int`
- `bool`
- `enum`
- `path`

### `content.interact` CLI 编码

`content.interact` 采用两段式解析：

1. 先解析通用参数：`--source --verb --ref`
2. 再按 source manifest 中该 verb 的 param schema 动态注册私有参数

私有参数编码规则固定为：

- 所有私有参数都映射为长选项，格式为 `--<param-name>`
- `param-name` 必须通过命名约束校验，且不能与 core 参数重名
- 标量参数：`--text "hello"`
- 可重复参数：重复传入同名选项，例如 `--attach a.pdf --attach b.pdf`
- 布尔参数：`--notify`
- enum 参数：仍使用 `--visibility public`，由 choices 校验

示例：

```bash
dc content interact --source rednote --verb comment --ref rednote:content/abc --text "这条不错"
dc content interact --source email --verb reply --ref email:content/msg-001 --body "收到" --attach ./a.pdf --attach ./b.pdf
```

## help 生成

help 由三层组成：

### 第一层：core 固定帮助

由 CLI 维护稳定语义：

- 命令的核心语义
- `search/update/query/interact` 边界
- 通用 option 含义

### 第二层：manifest 自动拼接

自动生成：

- source 简介
- mode 列表与当前 effective mode
- 支持的 source actions
- 每个 source action 支持的 options
- query 相关本地能力
- interaction verbs 与 verb params
- config 字段
- 哪些字段在当前 mode 下可见或必需
- 哪些能力仅因缺配置而暂不可执行

### 第三层：source 补充文档

只保留 source 特有信息：

- 站点限制
- 风控说明
- 获取 cookie 或凭证的方式
- 特殊例子

### 输出原则

- help 仅隐藏当前 mode 永远无效的 option / verb / param
- 仅因缺配置而暂不可执行的能力必须展示并标记原因
- 如果 source 没有实现某 action，help 不假装它支持
- source 不需要在多地重复维护相同能力说明文本

## source 自动注册

新增 source 时不再修改 `core/registry.py`。

### 自动发现规则

- 扫描 `sources/*/source.py`
- 导入模块后只读取 `MANIFEST` 与 `SOURCE_CLASS`
- `SOURCE_CLASS.name` 必须等于 `MANIFEST.identity.name`
- 每个模块只能提供一个 source
- 每个 source 名只能注册一次
- 校验 manifest 合法性
- 通过校验后自动注册到 registry

### 失败规则

- 模块导入失败：registry 初始化直接失败
- 缺少 `MANIFEST` 或 `SOURCE_CLASS`：直接失败
- `SOURCE_CLASS.name` 与 manifest 名不一致：直接失败
- 重复 source 名：直接失败
- manifest 字段非法：直接失败

不做“跳过坏 source 继续启动”的兜底逻辑。

### source 开发流程

新增一个 source 的标准路径：

1. 新建 `sources/<name>/source.py`
2. 声明 manifest
3. 实现 source class
4. 不修改 core 注册代码

## `BaseSource` 执行接口

重构后的 `BaseSource` 只暴露 source 执行接口，不承载 `content.query` 与 `sub.*` 这类纯本地命令。

建议保留的抽象方法：

- `resolve_mode() -> str`
- `health() -> HealthRecord`
- `list_channels() -> list[ChannelRecord]`
- `search_channels(query: str, limit: int) -> list[ChannelRecord]`
- `search_content(channel_key: str | None, query: str | None, since: datetime | None, limit: int) -> list[SearchResult]`
- `fetch_content(channel_key: str, since: datetime | None, limit: int | None, fetch_all: bool) -> list[ContentRecord]`
- `interact(verb: str, refs: list[str], params: dict[str, object]) -> list[InteractionResult]`
- `parse_content_ref(ref: str) -> str`

最小输出模型约束：

- `ChannelRecord` 至少包含 `source/channel_id/channel_key/display_name/url`
- `channel search` 直接返回 `ChannelRecord`，搜索附加信息放入 `ChannelRecord.metadata`
- `SearchResult` 只用于 `content search`，至少包含 `source/result_kind/title/url/content_ref`
- `ContentRecord` 至少包含 `source/channel_key/content_ref/title/url/published_at/fetched_at/raw_payload`
- `InteractionResult` 至少包含 `ref/verb/status/error`

约束：

- 输入参数由 core 完成基础校验后再传给 source
- source 返回的 `ContentRecord` 必须满足 `storage.required_record_fields`
- `parse_content_ref()` 接收完整 ref，返回 source 私有 opaque id，解析失败直接抛统一错误
- source 不直接操作 store，不自己解析 group/sub/config CLI 语义

## 统一错误契约

source 抛出的协议错误至少分为：

- `UnsupportedActionError`
- `UnsupportedOptionError`
- `MissingConfigError`
- `InvalidChannelError`
- `InvalidContentRefError`
- `AuthRequiredError`
- `RemoteExecutionError`

core 负责把它们格式化成统一 CLI 错误输出。

## 存储模型

### 保留 source 分表

内容记录继续按 source 分表存储。这个方向保留，不回退统一大表。

### `content_ref`

所有 content 需要一等稳定标识：

```text
<source>:content/<percent-encoded-source-id>
```

例如：

- `x:content/1891234567890`
- `rednote:content/67abcedf`

规则：

- `source` 部分直接使用 `SourceIdentity.name`
- `<percent-encoded-source-id>` 使用 UTF-8 字节序列做 RFC 3986 percent-encoding
- unreserved 字符 `A-Z a-z 0-9 - . _ ~` 必须保持原样
- 其余字节必须编码为大写十六进制 `%XX`
- core 不做二次规范化；同一个 opaque id 的 canonical ref 只有一种编码结果
- core 只校验：
  - 前缀 source 是否存在且合法
  - 是否包含固定分隔 `:content/`
  - percent-encoding 是否合法
- source 负责：
  - 解码后的 opaque id 是否属于自己
  - 该 ref 是否可被当前 verb/接口接受

`content_ref` 用于：

- search 结果定位
- 本地落库记录定位
- `content.interact` 目标定位
- 审计日志目标定位

`content_ref` 只是可执行引用，不是新的核心资源，也不能作为 `group/sub/channel` 的通用 target 类型。

`content_ref` 既可来自本地库记录，也可来自远端 search 结果；core 不要求它必须先落库。

### 记录字段调整

本地 content 记录需要额外持久化 `content_ref`。

`external_id` 仍可保留给 source 内部使用，但 core 层面对外统一以 `content_ref` 作为可执行引用。

## 订阅边界

### update 权限规则

- 未订阅 channel 禁止 `content update`
- `content update --source foo` 只更新 `foo` 的已订阅 channel
- `content update --group g` 展开后只允许已订阅目标
- group 中显式 `channel` 成员如果未订阅，直接报错
- 不允许“顺手 update 一次就落库”
- 展开后如果没有任何 concrete channel target，直接报错，不把它当作成功 no-op

### group 展开规则

- `source` 成员展开为该 source 当前已订阅 channels
- `channel` 成员直接作为候选目标
- 展开后去重
- 去重后做订阅校验
- `--dry-run` 展示最终具体目标

## 行为审计

必须新增统一行为审计，至少覆盖：

- `content.update`
- `content.interact`

### 审计字段

- `executed_at`
- `action`
- `source`
- `mode`
- `target_kind`
- `targets`
- `params_summary`
- `status`
- `error`
- `dry_run`

### 原则

- 审计是 core 行为，不是 source 自己随意打印日志
- 失败行为也要记录
- 批量操作要能看出具体目标集
- `content.update` 使用 `target_kind=channel`
- `content.interact` 使用 `target_kind=content_ref`

## 错误模型

需要统一几类错误输出：

- source 不支持某 action
- source 支持 action，但当前 mode 不支持
- action 支持，但某 option 不支持
- 配置缺失
- 配置类型错误
- `content update` 目标未订阅
- `content interact` refs 跨 source
- `content interact` verb 未声明
- verb param 校验失败

错误信息必须清楚指出：

- source
- action
- option 或 verb
- 缺失的 config key

## 实现边界

### core 负责

- 命令结构
- manifest 解析与校验
- effective capability 解析
- config schema 校验
- help 生成
- 自动注册
- 行为审计
- 存储与订阅边界 enforcement

### source 负责

- 远端请求
- HTML/API/浏览器自动化逻辑
- 数据归一化
- source 私有 verb 执行
- `content_ref` 的生成与解析

## 验收标准

重构完成后，至少满足：

- 不再存在 `--type`
- `channel search` 与 `content search` 分离
- 新 source 不需要修改 core registry
- source help/config/check 基于 manifest 自动生成
- `content update` 无法更新未订阅 channel
- `content search` 永不落库
- `content interact` 能基于 manifest 校验 verb 与 verb params
- CLI 能显示当前 effective mode
- option 不支持时直接报错，不静默忽略

## 测试要求

实现阶段必须包含：

- core capability 解析单元测试
- config schema 校验测试
- help 自动生成测试
- 自动注册测试
- update 订阅边界测试
- `content_ref` 与 `content.interact` 协议测试
- 基于真实 CLI 调用形式的端到端测试

端到端测试要求模拟用户实际 CLI 操作，而不是只测内部函数。

## 规划拆分

这份设计是统一架构设计，但 implementation plan 必须拆成两个计划域，不做一个大而散的总计划。

### 计划域 A：CLI + manifest + capability

- 资源优先命令面
- 去掉 `--type`
- `channel/content` 命名空间切换
- `SourceManifest`
- `mode`
- config schema
- help 生成
- 自动注册
- update 订阅边界

### 计划域 B：`content_ref` + interact + audit

- `content_ref`
- `content.interact`
- verb param 动态解析
- 行为审计

计划域 B 依赖计划域 A 的 manifest 与 capability 基础能力，但需要独立 planning 与独立测试。
