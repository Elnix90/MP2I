"""Render visual tool handler — generates charts, tables, and diagrams."""

import json
import tempfile
from pathlib import Path

from utils.logger import get_logger

logger = get_logger()


async def render_visual(
    type: str,
    title: str,
    data: dict,
    options: dict | None = None,
) -> str:
    options = options or {}

    if type == "table":
        return await _render_table(title, data)
    if type in ("bar", "line", "pie", "scatter"):
        return await _render_chart(type, title, data, options)
    if type == "diagram":
        return await _render_mermaid(title, data, options)

    return json.dumps({"error": f"Unknown visual type: {type}"}, ensure_ascii=False)


async def _render_table(title: str, data: dict) -> str:
    headers = data.get("headers", [])
    rows = data.get("rows", [])
    if not headers or not rows:
        return json.dumps({"error": "Table needs headers and rows"}, ensure_ascii=False)

    from utils.handlers.table import _render_table_image

    alignments = ["left"] * len(headers)
    buf, _ = _render_table_image(headers, rows, alignments)
    path = Path(tempfile.mktemp(suffix=".png"))
    path.write_bytes(buf.read())
    return json.dumps({"success": True, "type": "table", "image_path": str(path), "title": title}, ensure_ascii=False)


async def _render_chart(chart_type: str, title: str, data: dict, options: dict) -> str:
    try:
        import matplotlib  # type: ignore[import-untyped]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-untyped]

        plt.rcParams.update(
            {
                "figure.facecolor": "#0d0d0d",
                "axes.facecolor": "#1a1a19",
                "axes.edgecolor": "#383835",
                "text.color": "#ebebe8",
                "axes.labelcolor": "#ebebe8",
                "xtick.color": "#c3c3b7",
                "ytick.color": "#c3c3b7",
                "grid.color": "#383835",
                "font.size": 12,
            }
        )

        fig, ax = plt.subplots(figsize=(10, 6))

        labels = data.get("labels", [])
        datasets = data.get("datasets", [])

        if chart_type == "bar":
            x = range(len(labels))
            width = 0.8 / max(len(datasets), 1)
            for i, ds in enumerate(datasets):
                offset = (i - len(datasets) / 2 + 0.5) * width
                ax.bar([xi + offset for xi in x], ds.get("values", []), width, label=ds.get("label", ""))
            ax.set_xticks(list(x))
            ax.set_xticklabels(labels, rotation=45, ha="right")
            if len(datasets) > 1:
                ax.legend()

        elif chart_type == "line":
            for ds in datasets:
                ax.plot(labels, ds.get("values", []), marker="o", label=ds.get("label", ""))
            if len(datasets) > 1:
                ax.legend()

        elif chart_type == "pie":
            values = datasets[0].get("values", []) if datasets else []
            colors = ["#3987e5", "#2ecc71", "#e74c3c", "#f1c40f", "#9b59b6", "#1abc9c", "#e67e22", "#34495e"]
            _, _, autotexts = ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                colors=colors[: len(values)],
                textprops={"color": "#ebebe8"},
            )
            for t in autotexts:
                t.set_color("#0d0d0d")
                t.set_fontweight("bold")

        elif chart_type == "scatter":
            for ds in datasets:
                ax.scatter(ds.get("x", []), ds.get("y", []), label=ds.get("label", ""), s=60, alpha=0.8)
            if len(datasets) > 1:
                ax.legend()

        ax.set_title(title, fontsize=16, fontweight="bold", pad=15)
        if options.get("x_label"):
            ax.set_xlabel(options["x_label"])
        if options.get("y_label"):
            ax.set_ylabel(options["y_label"])
        ax.grid(True, alpha=0.3)

        if options.get("caption"):
            fig.text(0.5, 0.01, options["caption"], ha="center", fontsize=9, color="#c3c3b7")

        fig.tight_layout()
        path = Path(tempfile.mktemp(suffix=".png"))
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        return json.dumps({"success": True, "type": chart_type, "image_path": str(path), "title": title}, ensure_ascii=False)

    except ImportError:
        return json.dumps({"error": "matplotlib not installed"}, ensure_ascii=False)
    except Exception as exc:
        logger.error("Chart render failed: %s", exc)
        return json.dumps({"error": f"Chart render failed: {exc}"}, ensure_ascii=False)


async def _render_mermaid(title: str, data: dict, options: dict) -> str:
    source = data if isinstance(data, str) else data.get("source", "")
    if not source:
        return json.dumps({"error": "Mermaid source is required"}, ensure_ascii=False)

    try:
        import matplotlib  # type: ignore[import-untyped]

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt  # type: ignore[import-untyped]

        fig, ax = plt.subplots(figsize=(12, 8))
        ax.text(0.5, 0.5, f"Mermaid:\n{source}", ha="center", va="center", fontsize=10, family="monospace", color="#ebebe8", transform=ax.transAxes, wrap=True)
        ax.set_title(title, fontsize=16, fontweight="bold", pad=15)
        ax.axis("off")
        fig.patch.set_facecolor("#0d0d0d")

        path = Path(tempfile.mktemp(suffix=".png"))
        fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        return json.dumps({"success": True, "type": "diagram", "image_path": str(path), "title": title, "note": "Mermaid rendering requires mmdc CLI for full support"}, ensure_ascii=False)

    except ImportError:
        return json.dumps({"error": "matplotlib not installed"}, ensure_ascii=False)
    except Exception as exc:
        logger.error("Mermaid render failed: %s", exc)
        return json.dumps({"error": f"Mermaid render failed: {exc}"}, ensure_ascii=False)
