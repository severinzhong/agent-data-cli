from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
from pathlib import Path
import sys
from types import ModuleType

from core.base import BaseSource
from core.manifest import SourceManifest

@dataclass(frozen=True, slots=True)
class DiscoveredSourceModule:
    name: str
    module: ModuleType
    manifest: SourceManifest
    source_class: type[BaseSource]


def discover_source_modules(sources_dir: Path) -> list[DiscoveredSourceModule]:
    if not sources_dir.exists():
        return []
    discovered: list[DiscoveredSourceModule] = []
    for source_file in sorted(sources_dir.glob("*/source.py")):
        try:
            module = _load_module(sources_dir, source_file)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"failed to import source module: {source_file}") from exc
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
    return discovered


def _load_module(sources_dir: Path, source_file: Path) -> ModuleType:
    root_package_init = sources_dir / "__init__.py"
    if root_package_init.exists() and sources_dir.name == "sources":
        module_name = f"{sources_dir.name}.{source_file.parent.name}.source"
        return importlib.import_module(module_name)
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
