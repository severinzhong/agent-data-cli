from __future__ import annotations

from rich.console import Console

from core.help import HelpDoc, HelpSection


COMMAND_HELP: dict[str, HelpDoc] = {
    "query": HelpDoc(
        title="query",
        summary="从本地数据库读取记录并按条件过滤 (local database query).",
        sections=[
            HelpSection(
                title="语义",
                lines=[
                    "query 永远只读取本地数据库。",
                    "--keywords 只是过滤条件，不会触发远端搜索。",
                    "默认按 published_at 从新到旧排序。",
                ],
            ),
            HelpSection(
                title="常用参数",
                lines=[
                    "--source",
                    "--channel",
                    "--group",
                    "--keywords",
                    "--type",
                    "--since",
                    "--limit",
                    "--all",
                ],
            ),
            HelpSection(
                title="Examples",
                lines=[
                    "dc query --source bbc --limit 20",
                    "dc query --group middle-east --keywords 伊朗 --limit 20",
                    "dc query --source ashare --channel sh600519 --limit 30",
                ],
            ),
        ],
    ),
    "search": HelpDoc(
        title="search",
        summary="对单个 source 执行远端发现动作。",
        sections=[
            HelpSection(
                title="语义",
                lines=[
                    "search 走远端 source，不查本地数据库。",
                    "搜索结果可以是 channel 或 content。",
                ],
            ),
            HelpSection(
                title="Examples",
                lines=[
                    "dc search ashare 中国移动",
                    "dc search bbc openai --limit 5",
                ],
            ),
        ],
    ),
    "update": HelpDoc(
        title="update",
        summary="从远端 source 拉取数据并写入本地数据库。",
        sections=[
            HelpSection(
                title="语义",
                lines=[
                    "支持单 source/channel 更新。",
                    "支持 --group 批量更新。",
                    "--dry-run 只展示将要执行的具体目标。",
                ],
            ),
            HelpSection(
                title="Examples",
                lines=[
                    "dc update ashare --channel sh600519 --limit 30",
                    "dc update --group news --since 20260308",
                    "dc update --group stocks --dry-run",
                ],
            ),
        ],
    ),
    "sub": HelpDoc(
        title="sub",
        summary="管理本地订阅列表。",
        sections=[
            HelpSection(
                title="语义",
                lines=[
                    "sub add/remove/list 都只操作本地数据库。",
                    "sub add 可用 --name 覆盖默认 display_name。",
                ],
            ),
            HelpSection(
                title="Examples",
                lines=[
                    "dc sub add ashare sh000001 --name 上证指数",
                    "dc sub remove bbc world",
                    "dc sub list --source ashare",
                ],
            ),
        ],
    ),
}


def build_global_help_doc() -> HelpDoc:
    return HelpDoc(
        title="data-cli",
        summary="统一的多信息源 CLI。",
        sections=[
            HelpSection(
                title="命令速览",
                lines=[
                    "source: 查看 source 列表和健康状态。例：dc source list",
                    "channel: 查看 channel 列表。例：dc channel list <source>",
                    "group: 管理分组。例：dc group list",
                    "search: 对单个 source 做远端发现。例：dc search <source> <query>",
                    "sub: 管理订阅。例：dc sub list",
                    "update: 从远端拉取并入库。例：dc update <source> 或 dc update --group <group>",
                    "query: 查询本地数据库。例：dc query --limit 20",
                    "config: 管理 source 配置。例：dc config list",
                    "help: 查看帮助。例：dc help query 或 dc help <source>",
                ],
            ),
            HelpSection(
                title="Examples",
                lines=[
                    "dc help",
                    "dc help search",
                    "dc help query",
                    "dc help <source>",
                    "dc update --group <group> --dry-run",
                    "dc query --keywords <keywords> --limit 20",
                ],
            ),
        ],
    )


def build_command_help_doc(command: str) -> HelpDoc:
    try:
        return COMMAND_HELP[command]
    except KeyError as exc:
        raise RuntimeError(f"unknown help topic: {command}") from exc


def build_source_help_doc(source) -> HelpDoc:
    source_help = source.get_help()
    if source_help is None:
        source_help = HelpDoc(
            title=source.display_name or source.name,
            summary=source.description,
            sections=[],
        )

    supported_actions = []
    if source.describe().supports_search:
        supported_actions.append("search")
    if source.describe().supports_subscriptions:
        supported_actions.extend(["subscribe", "unsubscribe", "list_subscriptions"])
    if source.describe().supports_updates:
        supported_actions.append("update")
    if source.describe().supports_query:
        supported_actions.append("query")

    dynamic_sections = [
        HelpSection(
            title="Supported Actions",
            lines=supported_actions,
        ),
    ]

    config_specs = source.config_spec()
    if config_specs:
        dynamic_sections.append(
            HelpSection(
                title="Config",
                lines=[
                    f"{spec.key} ({spec.value_type}){' [required]' if spec.required else ''}"
                    for spec in config_specs
                ],
            )
        )

    record_types = source.get_supported_record_types()
    if record_types:
        dynamic_sections.append(
            HelpSection(
                title="Types",
                lines=list(record_types),
            )
        )

    return HelpDoc(
        title=source_help.title,
        summary=source_help.summary,
        sections=[*source_help.sections, *dynamic_sections],
    )


def render_help_doc(console: Console, doc: HelpDoc) -> None:
    console.print(f"[bold]{doc.title}[/bold]")
    console.print(doc.summary)
    for section in doc.sections:
        console.print()
        console.print(f"[bold]{section.title}[/bold]")
        for line in section.lines:
            console.print(f"- {line}")


def print_help_doc(doc: HelpDoc) -> None:
    console = Console()
    render_help_doc(console, doc)
