#!/usr/bin/env python3
"""
Telegram GitHub Repository Release Watcher Bot
Author: Christian / Prigma Software
License: MIT

A lightweight, multi-repository GitHub release monitor bot for Telegram.
- Monitors public and private GitHub repositories for new releases/tags/commits.
- Real-time interactive Telegram commands (/list, /add, /disable, /enable, /remove, /check).
- Ultra low-resource footprint (~15MB RAM, 0.0% CPU).
- Zero external Python dependencies (Standard Library only).
"""

import os
import sys
import time
import json
import logging
import urllib.request
import urllib.parse
from pathlib import Path
from tasks_watcher import PrigmaTasksWatcher

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "watched_repos.json" if DATA_DIR.exists() else BASE_DIR / "watched_repos.json"

# Logging configuration
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)

# Defaults
DEFAULT_CHECK_INTERVAL_SECONDS = 7200  # 2 hours


def load_env():
    """Load variables from .env file if available."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    if key not in os.environ:
                        os.environ[key] = val


def get_config():
    load_env()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    github_token = os.environ.get("GITHUB_TOKEN", "").strip()
    pragma_api_url = os.environ.get("PRIGMA_API_URL", "http://localhost:3000").strip()
    pragma_api_key = os.environ.get("PRIGMA_INTERNAL_API_KEY", "prigma_secret_internal_key_2026").strip()

    if not bot_token:
        logging.error("TELEGRAM_BOT_TOKEN is not defined in .env or environment!")
        sys.exit(1)

    try:
        interval = int(os.environ.get("CHECK_INTERVAL_SECONDS", DEFAULT_CHECK_INTERVAL_SECONDS))
    except ValueError:
        interval = DEFAULT_CHECK_INTERVAL_SECONDS

    return bot_token, chat_id, github_token, interval, pragma_api_url, pragma_api_key


def load_watched_repos():
    """Load watched repositories from local JSON state."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error reading {CONFIG_FILE}: {e}")
        return {}


def save_watched_repos(repos):
    """Persist watched repositories to local JSON state."""
    try:
        if not CONFIG_FILE.parent.exists():
            CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(repos, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Error saving {CONFIG_FILE}: {e}")


def clean_html(text):
    """Sanitize text for Telegram HTML parse mode."""
    if not text:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_github_headers(github_token=""):
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "Telegram-Repo-Watcher-Bot",
    }
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    return headers


def fetch_github_release(repo, github_token=""):
    """Fetch latest release, tag or commit from GitHub API."""
    headers = build_github_headers(github_token)
    
    # 1. Try releases
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                return json.loads(response.read().decode("utf-8"))
    except Exception:
        pass

    # 2. Fallback to tags
    tags_url = f"https://api.github.com/repos/{repo}/tags"
    try:
        req_tags = urllib.request.Request(tags_url, headers=headers)
        with urllib.request.urlopen(req_tags, timeout=12) as res_tags:
            tags = json.loads(res_tags.read().decode("utf-8"))
            if tags and len(tags) > 0:
                latest_tag = tags[0]
                return {
                    "tag_name": latest_tag["name"],
                    "name": latest_tag["name"],
                    "html_url": f"https://github.com/{repo}/releases/tag/{latest_tag['name']}",
                    "published_at": "",
                    "body": "Nuevo tag publicado en el repositorio.",
                }
    except Exception:
        pass

    # 3. Fallback to commits (for repos without releases/tags)
    commits_url = f"https://api.github.com/repos/{repo}/commits"
    try:
        req_commits = urllib.request.Request(commits_url, headers=headers)
        with urllib.request.urlopen(req_commits, timeout=12) as res_commits:
            commits = json.loads(res_commits.read().decode("utf-8"))
            if commits and len(commits) > 0:
                c = commits[0]
                sha_short = c["sha"][:7]
                msg = c.get("commit", {}).get("message", "Commit inicial")
                author = c.get("commit", {}).get("author", {}).get("name", "")
                date_str = c.get("commit", {}).get("author", {}).get("date", "")[:10]
                return {
                    "tag_name": f"commit-{sha_short}",
                    "name": f"Commit {sha_short}",
                    "html_url": c.get("html_url", f"https://github.com/{repo}"),
                    "published_at": date_str,
                    "body": f"<b>Autor:</b> {clean_html(author)}\n<b>Mensaje:</b> {clean_html(msg)}",
                }
    except Exception as e:
        logging.warning(f"Could not fetch commits for {repo}: {e}")

    return None


def send_telegram(bot_token, chat_id, text, disable_preview=True):
    """Send message to Telegram with HTML formatting."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res.get("ok", False)
    except Exception as e:
        logging.error(f"Error sending Telegram message: {e}")
        return False


def format_release_alert(repo, release, display_name=None):
    """Format rich notification message for Telegram."""
    tag = release.get("tag_name", "Desconocida")
    name = release.get("name") or tag
    url = release.get("html_url", f"https://github.com/{repo}/releases")
    published_at = release.get("published_at", "")[:10]
    raw_body = release.get("body", "Sin notas de versión disponibles.")

    body_clean = clean_html(raw_body) if not raw_body.startswith("<b>") else raw_body
    if len(body_clean) > 2800:
        body_clean = body_clean[:2800] + "\n\n<i>... [Ver changelog completo en GitHub]</i>"

    repo_title = display_name if display_name else repo

    return (
        f"🚀 <b>¡NUEVA ACTUALIZACIÓN DETECTADA!</b>\n\n"
        f"📦 <b>Repositorio:</b> <code>{clean_html(repo)}</code> ({clean_html(repo_title)})\n"
        f"🏷️ <b>Versión / Tag:</b> <code>{clean_html(tag)}</code>\n"
        f"📅 <b>Fecha:</b> {published_at if published_at else 'Reciente'}\n"
        f"🔗 <b>Enlace oficial:</b> <a href='{url}'>Ver en GitHub</a>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 <b>Detalles:</b>\n\n"
        f"{body_clean}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡️ <i>Telegram Repo Watcher Bot</i>"
    )


def check_all_repos(bot_token, chat_id, github_token="", notify_if_current=False):
    """Scan all active repositories for new updates."""
    repos = load_watched_repos()
    updates_found = 0
    checked_count = 0
    target_chats = [c.strip() for c in str(chat_id).split(",") if c.strip()]

    for repo, data in repos.items():
        if not data.get("enabled", True):
            continue

        checked_count += 1
        logging.info(f"Checking updates for {repo}...")
        release = fetch_github_release(repo, github_token)
        if not release:
            continue

        latest_tag = release.get("tag_name")
        last_known = data.get("last_release")

        if latest_tag and latest_tag != last_known:
            updates_found += 1
            logging.info(f"New release found for {repo}: {latest_tag} (was {last_known})")
            msg = format_release_alert(repo, release, data.get("name"))
            for cid in target_chats:
                send_telegram(bot_token, cid, msg)
            data["last_release"] = latest_tag
            save_watched_repos(repos)
        else:
            logging.info(f"{repo} is up to date ({latest_tag}).")

    if notify_if_current and updates_found == 0:
        for cid in target_chats:
            send_telegram(
                bot_token,
                cid,
                f"✅ <b>Todos los repositorios ({checked_count}) están al día.</b> No hay nuevas versiones por el momento.",
            )


def handle_telegram_command(bot_token, chat_id, text, github_token="", tasks_watcher: PrigmaTasksWatcher = None, from_id: str = ""):
    """Handle interactive user commands in Telegram."""
    text = text.strip()
    parts = text.split()
    cmd = parts[0].lower() if parts else ""
    if "@" in cmd:
        cmd = cmd.split("@")[0]
    args = parts[1:] if len(parts) > 1 else []
    repos = load_watched_repos()

    if cmd in ["/start", "/help"]:
        help_msg = (
            "🤖 <b>PRIGMA Bot - Panel de Control</b>\n\n"
            "<b>📦 Repositorios GitHub:</b>\n"
            "📋 <code>/list</code> - Ver repositorios monitoreados y su estado\n"
            "➕ <code>/add owner/repo</code> - Agregar un repositorio (ej: <code>/add n8n-io/n8n</code>)\n"
            "⏸️ <code>/disable owner/repo</code> - Pausar notificaciones de un repo\n"
            "▶️ <code>/enable owner/repo</code> - Reactivar notificaciones de un repo\n"
            "❌ <code>/remove owner/repo</code> - Eliminar un repo de la lista\n"
            "🔄 <code>/check</code> - Forzar verificación manual de repos\n\n"
            "<b>📋 Tareas PRIGMA:</b>\n"
            "🎯 <code>/tasks</code> - Ver mis tareas pendientes con botones interactivos\n"
            "👥 <code>/tasks_all</code> - Resumen general de tareas del equipo\n"
            "🔔 <code>/check_tasks</code> - Forzar envío de recordatorios de tareas"
        )
        send_telegram(bot_token, chat_id, help_msg)

    elif cmd in ["/tasks", "/mis_tareas"]:
        if not tasks_watcher:
            send_telegram(bot_token, chat_id, "⚠️ El servicio de tareas no está disponible.")
            return

        tasks = tasks_watcher.fetch_pending_tasks()
        # Filtrar tareas del usuario por su from_id o chat_id
        target_user_id = str(from_id or chat_id)
        user_tasks = [
            t for t in tasks
            if str((t.get("assignee_contact") or {}).get("telegram_chat_id")) == target_user_id
        ]

        if not user_tasks:
            send_telegram(bot_token, chat_id, "🎉 <b>¡Excelente trabajo!</b> No tienes tareas pendientes asignadas en este momento.")
            return

        send_telegram(bot_token, chat_id, f"📋 <b>Tienes {len(user_tasks)} tarea(s) activa(s):</b>")
        for t in user_tasks:
            msg = tasks_watcher.format_task_message(t)
            kb = tasks_watcher.generate_task_keyboard(str(t.get("id")))
            tasks_watcher.send_telegram_message(chat_id, msg, reply_markup=kb)

    elif cmd in ["/tasks_all", "/equipo"]:
        if not tasks_watcher:
            send_telegram(bot_token, chat_id, "⚠️ El servicio de tareas no está disponible.")
            return

        tasks = tasks_watcher.fetch_pending_tasks()
        if not tasks:
            send_telegram(bot_token, chat_id, "✅ No hay tareas pendientes en el equipo.")
            return

        lines = [f"📊 <b>Resumen General de Tareas ({len(tasks)} activas):</b>\n"]
        for t in tasks:
            assignee = t.get("assignee_name", "Sin asignar")
            code = t.get("task_code", "")
            title = t.get("title", "")
            status = t.get("status", "pending")
            lines.append(f"• <b>[{code}]</b> {title}\n  👤 <i>{assignee}</i> | Estado: <code>{status}</code>")

        send_telegram(bot_token, chat_id, "\n\n".join(lines))

    elif cmd == "/check_tasks":
        if not tasks_watcher:
            send_telegram(bot_token, chat_id, "⚠️ El servicio de tareas no está disponible.")
            return
        send_telegram(bot_token, chat_id, "🔄 <b>Verificando tareas pendientes y enviando recordatorios...</b>")
        sent = tasks_watcher.check_and_notify_tasks(force=True)
        send_telegram(bot_token, chat_id, f"✅ Verificación finalizada. Se enviaron <b>{sent}</b> recordatorio(s).")

    elif cmd == "/list":
        if not repos:
            send_telegram(bot_token, chat_id, "ℹ️ No tienes repositorios configurados aún. Usa <code>/add owner/repo</code> para agregar uno.")
            return

        lines = ["📋 <b>Repositorios en Monitoreo:</b>\n"]
        for repo, d in repos.items():
            status = "🟢 <b>Activo</b>" if d.get("enabled", True) else "⏸️ <b>Pausado</b>"
            last = d.get("last_release") or "Pendiente de primer escaneo"
            name = f" ({d.get('name')})" if d.get("name") and d.get("name") != repo else ""
            lines.append(f"• <code>{repo}</code>{name}\n  Estado: {status} | Última versión: <code>{last}</code>\n")

        lines.append("\n<i>Usa /disable &lt;repo&gt; o /enable &lt;repo&gt; para cambiar el estado.</i>")
        send_telegram(bot_token, chat_id, "\n".join(lines))

    elif cmd == "/add":
        if not args:
            send_telegram(bot_token, chat_id, "⚠️ Debes especificar el repositorio. Ejemplo:\n<code>/add n8n-io/n8n</code>")
            return
        repo = args[0].strip().replace("https://github.com/", "").strip("/")
        if "/" not in repo:
            send_telegram(bot_token, chat_id, "⚠️ Formato inválido. Debe ser <code>owner/repo</code> (ej. <code>chatwoot/chatwoot</code>).")
            return

        send_telegram(bot_token, chat_id, f"🔍 Verificando <code>{repo}</code> en GitHub...")
        release = fetch_github_release(repo, github_token)

        if not release:
            send_telegram(
                bot_token,
                chat_id,
                f"❌ <b>No se pudo acceder a</b> <code>{repo}</code>.\n\n"
                f"• Si el repo es <b>público</b>: Revisa que el nombre esté bien escrito.\n"
                f"• Si el repo es <b>privado</b>: Configura <code>GITHUB_TOKEN=ghp_xxx</code> en tu <code>.env</code> para darle permisos de lectura.",
            )
            return

        latest_tag = release.get("tag_name") or "v1.0.0"

        repos[repo] = {
            "name": repo,
            "enabled": True,
            "last_release": latest_tag,
        }
        save_watched_repos(repos)
        send_telegram(
            bot_token,
            chat_id,
            f"✅ <b>Repositorio agregado con éxito!</b>\n\n"
            f"📦 <code>{repo}</code>\n"
            f"🏷️ Versión / Commit actual: <code>{latest_tag}</code>\n"
            f"🔔 Notificaciones: <b>Activadas</b>",
        )

    elif cmd in ["/disable", "/pause"]:
        if not args:
            send_telegram(bot_token, chat_id, "⚠️ Especifica el repo. Ejemplo:\n<code>/disable chatwoot/chatwoot</code>")
            return
        repo = args[0].strip().replace("https://github.com/", "").strip("/")
        if repo in repos:
            repos[repo]["enabled"] = False
            save_watched_repos(repos)
            send_telegram(bot_token, chat_id, f"⏸️ <b>Notificaciones pausadas</b> para <code>{repo}</code>.")
        else:
            send_telegram(bot_token, chat_id, f"❌ El repositorio <code>{repo}</code> no está en la lista. Usa <code>/list</code> para ver tus repos.")

    elif cmd in ["/enable", "/resume"]:
        if not args:
            send_telegram(bot_token, chat_id, "⚠️ Especifica el repo. Ejemplo:\n<code>/enable chatwoot/chatwoot</code>")
            return
        repo = args[0].strip().replace("https://github.com/", "").strip("/")
        if repo in repos:
            repos[repo]["enabled"] = True
            save_watched_repos(repos)
            send_telegram(bot_token, chat_id, f"🟢 <b>Notificaciones reactivadas</b> para <code>{repo}</code>.")
        else:
            send_telegram(bot_token, chat_id, f"❌ El repositorio <code>{repo}</code> no está en la lista. Usa <code>/list</code>.")

    elif cmd in ["/remove", "/delete"]:
        if not args:
            send_telegram(bot_token, chat_id, "⚠️ Especifica el repo. Ejemplo:\n<code>/remove chatwoot/chatwoot</code>")
            return
        repo = args[0].strip().replace("https://github.com/", "").strip("/")
        if repo in repos:
            del repos[repo]
            save_watched_repos(repos)
            send_telegram(bot_token, chat_id, f"🗑️ <b>Repositorio eliminado</b> del monitoreo: <code>{repo}</code>.")
        else:
            send_telegram(bot_token, chat_id, f"❌ El repositorio <code>{repo}</code> no está en la lista.")

    elif cmd == "/check":
        send_telegram(bot_token, chat_id, "🔄 <b>Verificando todos los repositorios en GitHub...</b>")
        check_all_repos(bot_token, chat_id, github_token, notify_if_current=True)


def poll_telegram_updates(bot_token, chat_id, last_update_id):
    """Long-polling for Telegram updates."""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates?timeout=15&offset={last_update_id + 1}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Telegram-Repo-Watcher"})
        with urllib.request.urlopen(req, timeout=20) as response:
            res = json.loads(response.read().decode("utf-8"))
            if res.get("ok"):
                return res.get("result", [])
    except Exception:
        pass
    return []


def run_daemon():
    """Main daemon loop."""
    bot_token, chat_id, github_token, check_interval, pragma_api_url, pragma_api_key = get_config()
    logging.info(f"Starting Telegram Repo & Tasks Watcher Daemon (Interval: {check_interval}s / {check_interval//3600}h)...")
    last_update_id = 0
    last_check_time = time.time()
    last_task_check_time = 0

    tasks_watcher = PrigmaTasksWatcher(
        bot_token=bot_token,
        pragma_api_url=pragma_api_url,
        api_key=pragma_api_key,
        check_interval=check_interval,
    )

    # Initial check on startup
    check_all_repos(bot_token, chat_id, github_token, notify_if_current=False)
    tasks_watcher.check_and_notify_tasks(force=False)

    while True:
        try:
            # 1. Periodic release checks
            if time.time() - last_check_time >= check_interval:
                logging.info("Running scheduled check across all repos...")
                check_all_repos(bot_token, chat_id, github_token, notify_if_current=False)
                last_check_time = time.time()

            # 2. Periodic task reminder checks
            if time.time() - last_task_check_time >= check_interval:
                logging.info("Running scheduled check for PRIGMA tasks...")
                tasks_watcher.check_and_notify_tasks(force=False)
                last_task_check_time = time.time()

            # 3. Process incoming Telegram messages and button callbacks
            updates = poll_telegram_updates(bot_token, chat_id, last_update_id)
            target_chats = [c.strip() for c in str(chat_id).split(",") if c.strip()]
            for upd in updates:
                last_update_id = upd["update_id"]

                # Handle callback query (interactive buttons)
                if "callback_query" in upd:
                    tasks_watcher.handle_callback_query(upd["callback_query"])
                    continue

                # Handle text message
                msg = upd.get("message", {})
                from_id = str(msg.get("from", {}).get("id", ""))
                chat_id_msg = str(msg.get("chat", {}).get("id", from_id))
                text = msg.get("text", "")

                chat_type = msg.get("chat", {}).get("type", "")
                is_authorized = not target_chats or chat_id_msg in target_chats or from_id in target_chats or chat_type == "private"

                if text and is_authorized:
                    logging.info(f"Received command: {text} from {from_id} in {chat_id_msg}")
                    handle_telegram_command(bot_token, chat_id_msg, text, github_token, tasks_watcher=tasks_watcher, from_id=from_id)

        except KeyboardInterrupt:
            logging.info("Stopping bot daemon...")
            break
        except Exception as e:
            logging.error(f"Unexpected error in daemon loop: {e}")
            time.sleep(5)


if __name__ == "__main__":
    if "--daemon" in sys.argv or "-d" in sys.argv:
        run_daemon()
    elif "--check" in sys.argv or "-c" in sys.argv:
        token, cid, gtoken, _, _, _ = get_config()
        check_all_repos(token, cid, gtoken, notify_if_current=True)
    elif "--check-tasks" in sys.argv or "-t" in sys.argv:
        token, cid, gtoken, interval, purl, pkey = get_config()
        tw = PrigmaTasksWatcher(token, purl, pkey)
        tw.check_and_notify_tasks(force=True)
    else:
        token, cid, gtoken, _, _, _ = get_config()
        check_all_repos(token, cid, gtoken, notify_if_current=False)
