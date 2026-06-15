#!/usr/bin/env python3
"""
批量导入 Markdown 文档到 Milvus

用法:
    python scripts/batch_import.py /path/to/docs/
    python scripts/batch_import.py /path/to/docs/ --recursive
    python scripts/batch_import.py samples/
"""
import argparse
import sys
import time
from pathlib import Path

# 把项目根目录加入 Python 路径
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.models.schemas import DocumentMetadata, TaskStatus
from app.services.import_service import (
    get_task,
    process_batch_import,
    submit_import_task,
)


def collect_markdown_files(directory: Path, recursive: bool) -> list[Path]:
    if recursive:
        files = list(directory.rglob("*.md")) + list(directory.rglob("*.markdown"))
    else:
        files = list(directory.glob("*.md")) + list(directory.glob("*.markdown"))
    return sorted(set(files))


def main():
    parser = argparse.ArgumentParser(description="批量导入 Markdown 到旅游知识库")
    parser.add_argument("directory", help="包含 Markdown 文件的文件夹路径")
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="递归扫描子文件夹",
    )
    parser.add_argument(
        "--region",
        default="",
        help="统一设置地区元数据，如：张家界",
    )
    parser.add_argument(
        "--content-type",
        default="",
        help="统一设置内容类型，如：景点介绍",
    )
    args = parser.parse_args()

    directory = Path(args.directory).expanduser().resolve()
    if not directory.is_dir():
        print(f"错误: 目录不存在: {directory}")
        sys.exit(1)

    files = collect_markdown_files(directory, args.recursive)
    if not files:
        print(f"未找到 Markdown 文件: {directory}")
        sys.exit(1)

    settings = get_settings()
    if not settings.dashscope_api_key:
        print("错误: 请先在 .env 中配置 DASHSCOPE_API_KEY")
        sys.exit(1)

    metadata = DocumentMetadata(
        region=args.region,
        content_type=args.content_type,
    )

    print("=" * 50)
    print(f"  批量导入: {len(files)} 个文档")
    print(f"  目录: {directory}")
    print(f"  递归: {'是' if args.recursive else '否'}")
    print("=" * 50)
    print()

    batch_items = []
    task_ids = []

    for f in files:
        raw_bytes = f.read_bytes()
        task_id, raw_text, source_path = submit_import_task(
            settings, f.name, raw_bytes, metadata
        )
        batch_items.append((task_id, raw_text, f.name, source_path, metadata))
        task_ids.append(task_id)
        print(f"  已登记: {f.name} -> {task_id[:8]}...")

    print()
    print("开始处理（BGE-M3 首次加载较慢，请耐心等待）...")
    print()

    start = time.perf_counter()
    process_batch_import(settings, batch_items)
    elapsed = time.perf_counter() - start

    # 统计结果
    completed = failed = 0
    total_chunks = 0
    print()
    print("=" * 50)
    print("  导入结果")
    print("=" * 50)

    for tid in task_ids:
        doc = get_task(settings, tid)
        if not doc:
            continue
        status = doc["status"]
        name = doc.get("filename", tid)
        chunks = doc.get("inserted_chunks", 0)
        if status == TaskStatus.COMPLETED.value:
            completed += 1
            total_chunks += chunks
            print(f"  ✓ {name} -> {chunks} 条")
        else:
            failed += 1
            error = doc.get("error", "未知错误")
            print(f"  ✗ {name} -> {error[:80]}")

    print()
    print(f"  完成: {completed}/{len(files)}, 失败: {failed}")
    print(f"  总写入: {total_chunks} 条切片")
    print(f"  耗时: {elapsed:.1f}s")
    print("=" * 50)


if __name__ == "__main__":
    main()
