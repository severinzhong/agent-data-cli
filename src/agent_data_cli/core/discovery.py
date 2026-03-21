from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

from agent_data_cli.core.base import BaseSource
from agent_data_cli.core.manifest import SourceManifest


LEGACY_MODULE_ALIASES: dict[str, str] = {
    "core": "agent_data_cli.core",
    "core.base": "agent_data_cli.core.base",
    "core.capabilities": "agent_data_cli.core.capabilities",
    "core.config": "agent_data_cli.core.config",
    "core.discovery": "agent_data_cli.core.discovery",
    "core.help": "agent_data_cli.core.help",
    "core.manifest": "agent_data_cli.core.manifest",
    "core.models": "agent_data_cli.core.models",
    "core.protocol": "agent_data_cli.core.protocol",
    "core.registry": "agent_data_cli.core.registry",
    "core.source_defaults": "agent_data_cli.core.source_defaults",
    "fetchers": "agent_data_cli.fetchers",
    "fetchers.base": "agent_data_cli.fetchers.base",
    "fetchers.browser": "agent_data_cli.fetchers.browser",
    "fetchers.http": "agent_data_cli.fetchers.http",
    "fetchers.jina": "agent_data_cli.fetchers.jina",
    "store": "agent_data_cli.store",
    "store.db": "agent_data_cli.store.db",
    "utils": "agent_data_cli.utils",
    "utils.text": "agent_data_cli.utils.text",
    "utils.time": "agent_data_cli.utils.time",
    "utils.urls": "agent_data_cli.utils.urls",
}


@dataclass(frozen=True, slots=True)
class DiscoveredSourceModule:
    name: str
    module: ModuleType
    manifest: SourceManifest
    source_class: type[BaseSource]


@dataclass(frozen=True, slots=True)
class FailedSourceModule:
    name: str
    source_file: Path
    error: str


@dataclass(frozen=True, slots=True)
class SourceDiscoveryScan:
    discovered: list[DiscoveredSourceModule]
    failures: list[FailedSourceModule]


def discover_source_modules(sources_dir: Path) -> list[DiscoveredSourceModule]:
    scan = scan_source_modules(sources_dir)
    if scan.failures:
        first = scan.failures[0]
        raise RuntimeError(f"failed to import source module: {first.source_file}")
    return scan.discovered


def scan_source_modules(sources_dir: Path) -> SourceDiscoveryScan:
    if not sources_dir.exists():
        return SourceDiscoveryScan(discovered=[], failures=[])
    _install_legacy_module_aliases()
    discovered: list[DiscoveredSourceModule] = []
    failures: list[FailedSourceModule] = []
    for source_file in sorted(sources_dir.glob("*/source.py")):
        try:
            module = _load_module(sources_dir, source_file)
        except Exception as exc:  # noqa: BLE001
            failures.append(
                FailedSourceModule(
                    name=source_file.parent.name,
                    source_file=source_file,
                    error=f"{type(exc).__name__}: {exc}",
                )
            )
            continue
        if not hasattr(module, "MANIFEST"):
            raise RuntimeError(f"{source_file} must declare MANIFEST")
        if not hasattr(module, "SOURCE_CLASS"):
            raise RuntimeError(f"{source_file} must declare SOURCE_CLASS")
        manifest = module.MANIFEST
        source_class = module.SOURCE_CLASS
        if not isinstance(manifest, SourceManifest):
            raise RuntimeError(f"{source_file} MANIFEST must be SourceManifest")
        if not isinstance(source_class, type) or not issubclass(source_class, BaseSource):
            raise RuntimeError(f"{source_file} SOURCE_CLASS must inherit BaseSource")
        if source_class.name != manifest.identity.name:
            raise RuntimeError(
                f"{source_file} source name mismatch: {source_class.name} != {manifest.identity.name}"
            )
        discovered.append(
            DiscoveredSourceModule(
                name=source_file.parent.name,
                module=module,
                manifest=manifest,
                source_class=source_class,
            )
        )
    return SourceDiscoveryScan(discovered=discovered, failures=failures)


def _load_module(sources_dir: Path, source_file: Path) -> ModuleType:
    source_package_init = source_file.parent / "__init__.py"
    if source_package_init.exists():
        return _load_package_module(source_file.parent, source_file)
    module_name = f"core_discovery_{source_file.parent.name}"
    return _load_file_module(module_name, source_file)


def _load_package_module(source_dir: Path, source_file: Path) -> ModuleType:
    package_name = f"core_discovery_{source_dir.name}"
    package_init = source_dir / "__init__.py"
    package_spec = importlib.util.spec_from_file_location(
        package_name,
        package_init,
        submodule_search_locations=[str(source_dir)],
    )
    if package_spec is None or package_spec.loader is None:
        raise RuntimeError(f"failed to load source package: {source_dir}")
    package = importlib.util.module_from_spec(package_spec)
    sys.modules[package_name] = package
    try:
        package_spec.loader.exec_module(package)
        module_name = f"{package_name}.source"
        module = _load_file_module(module_name, source_file)
        sys.modules[module_name] = module
        return module
    except Exception:
        sys.modules.pop(package_name, None)
        sys.modules.pop(f"{package_name}.source", None)
        raise


def _load_file_module(module_name: str, source_file: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, source_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load source module: {source_file}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _install_legacy_module_aliases() -> None:
    for legacy_name, canonical_name in LEGACY_MODULE_ALIASES.items():
        if legacy_name in sys.modules:
            continue
        sys.modules[legacy_name] = importlib.import_module(canonical_name)
