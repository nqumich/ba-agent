"""
BA-Agent Memory CLI

命令行工具用于管理记忆系统索引和搜索
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click

from .index import (
    MemoryIndexer,
    open_index_db,
    get_index_db_path,
    DEFAULT_INDEX_PATH,
    ensure_memory_index_schema,
)
from .vector_search import HybridSearchEngine
from .embedding import create_embedding_provider
from .flush import MemoryFlush, MemoryExtractor


@click.group()
@click.version_option(version="1.0.0")
def memory():
    """BA-Agent 记忆管理 CLI

    管理记忆索引、搜索和 flush 功能
    """
    pass


@memory.command()
@click.option("--memory-dir", type=click.Path(exists=True), default="./memory", help="记忆目录路径")
@click.option("--index-path", type=click.Path(), default=None, help="索引文件路径（默认使用记忆目录下的 .index）")
@click.option("--force", is_flag=True, help="强制重建索引，即使已存在")
def index(memory_dir: str, index_path: Optional[str], force: bool):
    """重建记忆索引

    扫描 memory 目录下的所有文件并重建搜索索引
    """
    memory_path = Path(memory_dir)
    if not memory_path.exists():
        click.echo(f"❌ 记忆目录不存在: {memory_dir}", err=True)
        sys.exit(1)

    # 确定索引路径
    if index_path:
        idx_path = Path(index_path)
    else:
        idx_path = memory_path / ".index" / "memory.db"

    click.echo(f"📁 记忆目录: {memory_path}")
    click.echo(f"🗂️  索引路径: {idx_path}")

    # 创建索引器
    indexer = MemoryIndexer(
        memory_dir=memory_path,
        index_path=idx_path,
        force=force
    )

    try:
        # 执行索引
        with click.progressbar(
            length=100,
            label='📊 正在重建索引'
        ) as bar:
            stats = indexer.rebuild_index(
                progress_callback=lambda p: bar.update(p)
            )

        click.echo("\n✅ 索引重建完成")
        click.echo(f"   文件数: {stats.get('files', 0)}")
        click.echo(f"   分块数: {stats.get('chunks', 0)}")
        click.echo(f"   向量数: {stats.get('vectors', 0)}")

    except Exception as e:
        click.echo(f"\n❌ 索引失败: {e}", err=True)
        sys.exit(1)


@memory.command()
@click.argument("query")
@click.option("--max-results", "-n", type=int, default=10, help="最大结果数")
@click.option("--min-score", type=float, default=0.0, help="最小相关性分数")
@click.option("--source", type=click.Choice(["all", "memory", "sessions"]), default="all", help="来源过滤")
@click.option("--hybrid/--fts-only", default=True, help="是否使用混合搜索")
def search(query: str, max_results: int, min_score: float, source: str, hybrid: bool):
    """搜索记忆

    QUERY: 搜索关键词或自然语言查询
    """
    index_path = get_index_db_path()

    if not index_path.exists():
        click.echo(f"❌ 索引不存在: {index_path}", err=True)
        click.echo("   请先运行: ba-agent memory index")
        sys.exit(1)

    try:
        db = open_index_db(index_path)

        if hybrid:
            # 尝试混合搜索
            try:
                provider = create_embedding_provider(provider="auto")
                query_embedding = provider.encode_batch([query])[0]
                embedding_dims = len(query_embedding)

                engine = HybridSearchEngine(
                    db,
                    dims=embedding_dims,
                    use_sqlite_vec=False
                )
                engine.ensure_vector_tables()

                query_id = "__query__"
                engine.insert_vector(query_id, query_embedding)

                source_filter = None if source == "all" else [source]
                results = engine.search(
                    query=query,
                    query_embedding=query_embedding,
                    limit=max_results,
                    source_filter=source_filter
                )

                # 清理查询向量
                try:
                    engine.delete_by_path("")
                except:
                    pass

            except Exception as e:
                click.echo(f"⚠️  混合搜索失败，回退到 FTS: {e}", err=True)
                hybrid = False

        if not hybrid:
            # FTS 搜索
            like_query = f"%{query}%"
            sql = """
                SELECT
                    c.id, c.path, c.source,
                    c.start_line, c.end_line, c.text
                FROM chunks c
                WHERE c.text LIKE ?
            """
            params = [like_query]

            if source != "all":
                sql += " AND c.source = ?"
                params.append(source)

            sql += f" LIMIT {max_results}"

            cursor = db.execute(sql, params)
            rows = cursor.fetchall()

            results = []
            for row in rows:
                chunk_id, path, src, start_line, end_line, text = row
                match_count = text.lower().count(query.lower())
                score = min(1.0, match_count / 10.0)

                if score >= min_score:
                    results.append({
                        "id": chunk_id,
                        "path": path,
                        "source": src,
                        "start_line": start_line,
                        "end_line": end_line,
                        "text": text,
                        "score": score
                    })

        db.close()

        # 显示结果
        if not results:
            click.echo(f"❌ 未找到匹配 \"{query}\" 的结果")
            return

        click.echo(f"🔍 找到 {len(results)} 个匹配:\n")

        for i, result in enumerate(results, 1):
            score = result.get("score", 0)
            path = result.get("path", "")
            line = result.get("start_line", 0)
            text = result.get("text", "")

            click.echo(f"{i}. {path}:{line} (相关性: {score:.2f})")
            click.echo(f"   {text[:100]}...")
            click.echo()

    except Exception as e:
        click.echo(f"❌ 搜索失败: {e}", err=True)
        sys.exit(1)


@memory.command()
def status():
    """查看索引状态"""
    index_path = get_index_db_path()

    if not index_path.exists():
        click.echo(f"❌ 索引不存在: {index_path}")
        click.echo("\n请先运行: ba-agent memory index")
        return

    try:
        db = open_index_db(index_path)

        # 统计信息
        cursor = db.execute("SELECT COUNT(*) FROM files")
        file_count = cursor.fetchone()[0]

        cursor = db.execute("SELECT COUNT(*) FROM chunks")
        chunk_count = cursor.fetchone()[0]

        cursor = db.execute("SELECT COUNT(DISTINCT source) FROM chunks")
        source_count = cursor.fetchone()[0]

        # 检查向量表
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
        )
        has_vectors = cursor.fetchone() is not None

        vector_count = 0
        if has_vectors:
            cursor = db.execute("SELECT COUNT(*) FROM chunks_vec")
            vector_count = cursor.fetchone()[0]

        db.close()

        click.echo(f"📊 索引状态: {index_path}\n")
        click.echo(f"   文件数: {file_count}")
        click.echo(f"   分块数: {chunk_count}")
        click.echo(f"   来源数: {source_count}")
        click.echo(f"   向量数: {vector_count}")
        click.echo(f"   混合搜索: {'✅ 启用' if has_vectors and vector_count > 0 else '❌ 未启用'}")

    except Exception as e:
        click.echo(f"❌ 查询失败: {e}", err=True)
        sys.exit(1)


@memory.command()
@click.option("--config", type=click.Path(exists=True), default=None, help="配置文件路径")
def flush(config: Optional[str]):
    """手动触发 Memory Flush

    从当前会话中提取记忆并保存到磁盘
    """
    click.echo("⚠️  Memory Flush 需要在 Agent 上下文中运行")
    click.echo("   请在 Agent 会话中使用 memory_flush 工具")
    sys.exit(1)


@memory.command()
@click.argument("text")
@click.option("--type", "retain_type", type=click.Choice(["W", "B", "O", "S"]), required=True, help="Retain 类型")
@click.option("--entity", "-e", type=str, default=None, help="关联实体")
@click.option("--confidence", "-c", type=float, default=None, help="置信度 (仅用于 O 类型)")
def retain(text: str, retain_type: str, entity: Optional[str], confidence: Optional[float]):
    """格式化为 Retain 格式

    TEXT: 要格式化的内容

    示例:
        ba-agent memory retain "完成 GMV 检测" --type W --entity "数据团队"
        ba-agent memory retain "安全库存应保持 7 天以上" --type O --confidence 0.9
    """
    from .flush import RetainFormatter

    if retain_type == "W":
        result = RetainFormatter.format_world(text, entity)
    elif retain_type == "B":
        result = RetainFormatter.format_bio(text, entity)
    elif retain_type == "O":
        conf = confidence if confidence is not None else 0.5
        result = RetainFormatter.format_opinion(text, conf, entity)
    elif retain_type == "S":
        result = RetainFormatter.format_summary(text, entity)
    else:
        click.echo(f"❌ 无效的类型: {retain_type}", err=True)
        sys.exit(1)

    click.echo(result)


# 主入口
def main():
    """CLI 主入口"""
    memory()


if __name__ == "__main__":
    main()
