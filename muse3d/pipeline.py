from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .catalog import write_catalog
from .env import env_value
from .manifest import read_manifest, write_json
from .models import ArtworkManifest


@dataclass(slots=True)
class BuildOptions:
    dry_run: bool = False
    publish: bool = False
    skip_optimize: bool = False
    skip_validate: bool = False
    blender_path: str | None = None


@dataclass(slots=True)
class BuildResult:
    manifest: ArtworkManifest
    raw_glb: Path
    final_glb: Path
    metadata: Path
    validation_report: Path | None
    published_dir: Path | None


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def resolve_tool(name: str) -> str | None:
    return shutil.which(name)


def resolve_blender(root: Path, override: str | None = None) -> str | None:
    candidates = [
        override,
        env_value(root, "BLENDER_PATH"),
        shutil.which("blender"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(Path(candidate))
        if candidate and shutil.which(candidate):
            return str(candidate)
    return None


def muserag_ar_dir(root: Path) -> Path:
    configured = env_value(root, "MUSERAG_AR_DIR", "../museRAG/assets/ar")
    path = Path(configured or "../museRAG/assets/ar")
    return path if path.is_absolute() else (root / path).resolve()


def run_command(command: list[str], *, cwd: Path, dry_run: bool = False) -> None:
    printable = " ".join(f'"{part}"' if " " in part else part for part in command)
    if dry_run:
        print(f"[dry-run] {printable}")
        return

    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {printable}")


def build_export_config(
    root: Path,
    manifest: ArtworkManifest,
    raw_glb: Path,
) -> Path:
    source_path = manifest.source_abs_path(root)
    config_path = raw_glb.parent / "export-config.json"
    payload = {
        "source_path": str(source_path),
        "output_path": str(raw_glb),
        "object_names": manifest.source.object_names,
        "transform": {
            "scale": manifest.transform.scale,
            "position": manifest.transform.position,
            "rotation": manifest.transform.rotation,
            "center_to_origin": manifest.transform.center_to_origin,
            "apply_export_transform": manifest.transform.apply_export_transform,
        },
    }
    write_json(config_path, payload)
    return config_path


def export_raw_glb(
    root: Path,
    manifest: ArtworkManifest,
    raw_glb: Path,
    options: BuildOptions,
) -> None:
    source_path = manifest.source_abs_path(root)
    raw_glb.parent.mkdir(parents=True, exist_ok=True)

    if source_path.suffix.lower() == ".glb" and not manifest.source.blend:
        if options.dry_run:
            print(f"[dry-run] copy {source_path} -> {raw_glb}")
            return
        if not source_path.exists():
            raise FileNotFoundError(f"Source GLB not found: {source_path}")
        shutil.copy2(source_path, raw_glb)
        return

    blender = resolve_blender(root, options.blender_path)
    if not blender and not options.dry_run:
        raise RuntimeError(
            "Blender was not found. Set BLENDER_PATH in .env or pass --blender."
        )

    if not source_path.exists() and not options.dry_run:
        raise FileNotFoundError(f"3D source not found: {source_path}")

    config_path = raw_glb.parent / "export-config.json"
    if options.dry_run:
        print(f"[dry-run] write Blender export config -> {config_path}")
    else:
        config_path = build_export_config(root, manifest, raw_glb)
    script_path = root / "scripts" / "export_blender_glb.py"
    command = [
        blender or "blender",
        "--background",
        "--python",
        str(script_path),
        "--",
        "--config",
        str(config_path),
    ]
    run_command(command, cwd=root, dry_run=options.dry_run)


def optimize_glb(
    root: Path,
    manifest: ArtworkManifest,
    raw_glb: Path,
    final_glb: Path,
    options: BuildOptions,
) -> None:
    final_glb.parent.mkdir(parents=True, exist_ok=True)

    if options.skip_optimize or not manifest.optimization.enabled:
        if options.dry_run:
            print(f"[dry-run] copy {raw_glb} -> {final_glb}")
            return
        shutil.copy2(raw_glb, final_glb)
        return

    node = resolve_tool("node")
    if not node:
        raise RuntimeError("Node.js was not found. Install Node.js before optimizing GLB files.")

    script_path = root / "scripts" / "optimize_glb.mjs"
    command = [
        node,
        str(script_path),
        str(raw_glb),
        str(final_glb),
        "--texture-size",
        str(manifest.optimization.texture_size),
        "--texture-compress",
        manifest.optimization.texture_compress,
        "--compress",
        manifest.optimization.compress,
    ]
    if manifest.optimization.simplify:
        command.extend(["--simplify", "--simplify-ratio", str(manifest.optimization.simplify_ratio)])
    run_command(command, cwd=root, dry_run=options.dry_run)


def validate_glb(
    root: Path,
    final_glb: Path,
    options: BuildOptions,
) -> Path | None:
    if options.skip_validate:
        return None

    node = resolve_tool("node")
    if not node:
        raise RuntimeError("Node.js was not found. Install Node.js before validating GLB files.")

    report_path = final_glb.with_suffix(".validation.json")
    script_path = root / "scripts" / "validate_glb.mjs"
    command = [
        node,
        str(script_path),
        str(final_glb),
        "--report",
        str(report_path),
    ]
    run_command(command, cwd=root, dry_run=options.dry_run)
    return report_path


def write_artifact_metadata(manifest: ArtworkManifest, final_glb: Path, dry_run: bool) -> Path:
    metadata_path = final_glb.parent / "metadata.json"
    if dry_run:
        print(f"[dry-run] write metadata -> {metadata_path}")
        return metadata_path
    write_json(metadata_path, manifest.to_metadata())
    return metadata_path


def rebuild_catalog(root: Path, *, publish: bool = False, dry_run: bool = False) -> Path:
    catalog_path = root / "catalog" / "ar-catalog.json"
    if dry_run:
        print(f"[dry-run] write catalog -> {catalog_path}")
    else:
        write_catalog(root / "assets" / "dist" / "ar", catalog_path)

    if publish:
        target = muserag_ar_dir(root) / "catalog.json"
        if dry_run:
            print(f"[dry-run] copy {catalog_path} -> {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(catalog_path, target)
    return catalog_path


def publish_artifact(root: Path, manifest: ArtworkManifest, final_dir: Path, dry_run: bool) -> Path:
    target_dir = muserag_ar_dir(root) / manifest.museum_id / manifest.slug
    if dry_run:
        print(f"[dry-run] copytree {final_dir} -> {target_dir}")
        return target_dir

    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(final_dir, target_dir, dirs_exist_ok=True)
    rebuild_catalog(root, publish=True, dry_run=False)
    return target_dir


def build_manifest(manifest_path: Path, options: BuildOptions) -> BuildResult:
    root = project_root()
    manifest = read_manifest(manifest_path)
    work_dir = root / "assets" / "work" / manifest.slug
    raw_glb = work_dir / f"{manifest.slug}.raw.glb"
    final_dir = root / "assets" / "dist" / "ar" / manifest.museum_id / manifest.slug
    final_glb = final_dir / manifest.filename

    export_raw_glb(root, manifest, raw_glb, options)
    optimize_glb(root, manifest, raw_glb, final_glb, options)
    validation_report = validate_glb(root, final_glb, options)
    metadata_path = write_artifact_metadata(manifest, final_glb, options.dry_run)
    if not options.dry_run:
        rebuild_catalog(root)

    published_dir = None
    if options.publish:
        published_dir = publish_artifact(root, manifest, final_dir, options.dry_run)

    return BuildResult(
        manifest=manifest,
        raw_glb=raw_glb,
        final_glb=final_glb,
        metadata=metadata_path,
        validation_report=validation_report,
        published_dir=published_dir,
    )
