from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


def configure_task_label(label: QLabel) -> None:
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setOpenExternalLinks(False)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse)


def task_link(task_id: int, text: str) -> str:
    safe_text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return (
        f'<a href="task:{task_id}" '
        f'style="color:inherit; text-decoration:none; cursor:pointer;">{safe_text}</a>'
    )


def task_id_from_link(link: str) -> int | None:
    if not link.startswith("task:"):
        return None
    try:
        return int(link.split(":", 1)[1])
    except ValueError:
        return None
