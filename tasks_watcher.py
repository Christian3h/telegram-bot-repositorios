#!/usr/bin/env python3
"""
Módulo Watcher de Tareas PRIGMA para el Bot de Telegram.
Consulta el endpoint interno de PRIGMA, gestiona recordatorios en horario laboral,
envía mensajes con botones interactivos y procesa actualizaciones de estado.
"""

import os
import json
import time
import logging
import datetime
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATE_FILE = DATA_DIR / "task_reminders.json" if DATA_DIR.exists() else BASE_DIR / "task_reminders.json"

DEFAULT_TASK_CHECK_INTERVAL = 7200  # 2 horas
MIN_REMINDER_INTERVAL_HOURS = 3      # Espaciado mínimo por tarea para evitar saturar al empleado


class PrigmaTasksWatcher:
    def __init__(
        self,
        bot_token: str,
        pragma_api_url: str = "http://localhost:3000",
        api_key: str = "prigma_secret_internal_key_2026",
        check_interval: int = DEFAULT_TASK_CHECK_INTERVAL,
        working_hours_start: int = 8,
        working_hours_end: int = 18,
        working_days: tuple = (0, 1, 2, 3, 4),  # Lunes a Viernes (0=Lunes, 6=Domingo)
    ):
        self.bot_token = bot_token
        self.pragma_api_url = pragma_api_url.rstrip("/")
        self.api_key = api_key
        self.check_interval = check_interval
        self.working_hours_start = working_hours_start
        self.working_hours_end = working_hours_end
        self.working_days = working_days
        self.last_check_timestamp = 0
        self.reminders_state = self._load_state()

    def _load_state(self) -> dict:
        """Carga el registro de timestamps de recordatorios enviados por tarea."""
        if not STATE_FILE.exists():
            return {}
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[tasks_watcher] Error al leer {STATE_FILE}: {e}")
            return {}

    def _save_state(self):
        """Guarda el registro de recordatorios en disco."""
        try:
            if not STATE_FILE.parent.exists():
                STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.reminders_state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"[tasks_watcher] Error al guardar {STATE_FILE}: {e}")

    def is_working_hours(self, dt: datetime.datetime = None) -> bool:
        """Valida si el momento actual está dentro de la jornada laboral."""
        if dt is None:
            dt = datetime.datetime.now()
        # Verificar día de la semana (0=Lunes, 4=Viernes)
        if dt.weekday() not in self.working_days:
            return False
        # Verificar hora
        if not (self.working_hours_start <= dt.hour < self.working_hours_end):
            return False
        return True

    def _make_api_request(self, path: str, method: str = "GET", payload: dict = None) -> dict:
        """Realiza una petición HTTP autenticada a la API de PRIGMA."""
        url = f"{self.pragma_api_url}{path}"
        headers = {
            "x-api-key": self.api_key,
            "User-Agent": "PrigmaTelegramBot/1.0",
            "Content-Type": "application/json",
        }

        data = json.dumps(payload).encode("utf-8") if payload else None
        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            logging.error(f"[tasks_watcher] Error HTTP {e.code} en {path}: {err_body}")
            try:
                return json.loads(err_body)
            except Exception:
                return {"success": False, "error": f"HTTP {e.code}: {e.reason}"}
        except Exception as e:
            logging.error(f"[tasks_watcher] Error de conexión con PRIGMA ({url}): {e}")
            return {"success": False, "error": str(e)}

    def fetch_pending_tasks(self, assignee: str = None) -> list:
        """Consulta las tareas pendientes desde la API de PRIGMA."""
        path = "/api/internal/tasks/pending"
        params = []
        if assignee:
            params.append(f"assignee={urllib.parse.quote(assignee)}")
        if params:
            path += "?" + "&".join(params)

        res = self._make_api_request(path, method="GET")
        if res.get("success"):
            return res.get("tasks", [])
        return []

    def update_task_status(self, task_id: str, new_status: str, author_name: str = "Telegram User", note: str = None) -> dict:
        """Actualiza el estado de una tarea mediante la API de PRIGMA."""
        payload = {
            "task_id": task_id,
            "status": new_status,
            "updated_by": author_name,
            "note": note or f"Estado actualizado a '{new_status}' desde Telegram",
        }
        return self._make_api_request("/api/internal/tasks/update-status", method="POST", payload=payload)

    def send_telegram_message(self, chat_id: int | str, text: str, reply_markup: dict = None) -> dict:
        """Envía un mensaje con soporte para Inline Keyboard a Telegram."""
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logging.error(f"[tasks_watcher] Error enviando mensaje a Telegram chat {chat_id}: {e}")
            return {"ok": False, "error": str(e)}

    def answer_callback_query(self, callback_query_id: str, text: str = None, show_alert: bool = False):
        """Responde a un callback query de Telegram para cerrar el loader del botón."""
        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id, "show_alert": show_alert}
        if text:
            payload["text"] = text

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logging.error(f"[tasks_watcher] Error answering callback query: {e}")

    def generate_task_keyboard(self, task_id: str) -> dict:
        """Genera el teclado interactivo con botones de estado para una tarea."""
        return {
            "inline_keyboard": [
                [
                    {"text": "▶️ En Progreso", "callback_data": f"ts:{task_id}:in_progress"},
                    {"text": "🔍 En Revisión", "callback_data": f"ts:{task_id}:in_review"},
                ],
                [
                    {"text": "✅ Completar", "callback_data": f"ts:{task_id}:completed"},
                    {"text": "⚠️ Bloqueada", "callback_data": f"ts:{task_id}:blocked"},
                ],
            ]
        }

    def format_task_message(self, task: dict) -> str:
        """Construye el texto formateado en HTML para el recordatorio de tarea."""
        code = task.get("task_code", "TASK")
        title = task.get("title", "")
        status = task.get("status", "pending")
        priority = task.get("priority", "medium")
        due_date = task.get("due_date")
        assignee = task.get("assignee_name", "Sin asignar")

        status_emojis = {
            "pending": "⏳ Pendiente",
            "in_progress": "⚡ En Progreso",
            "in_review": "🔍 En Revisión",
            "completed": "✅ Completada",
            "blocked": "🚫 Bloqueada",
        }
        status_label = status_emojis.get(status, status)

        msg = (
            f"📋 <b>Recordatorio de Tarea [{code}]</b>\n\n"
            f"<b>Título:</b> {title}\n"
            f"<b>Estado:</b> {status_label}\n"
            f"<b>Prioridad:</b> {priority.upper()}\n"
        )
        if due_date:
            msg += f"<b>Fecha límite:</b> {due_date}\n"
        msg += f"\n👋 Hola <b>{assignee}</b>, ¿cómo va el avance de esta actividad? Actualiza su estado pulsando un botón:"

        return msg

    def check_and_notify_tasks(self, force: bool = False) -> int:
        """
        Revisa las tareas pendientes y envía recordatorios espaciados
        únicamente durante el horario laboral a los empleados vinculados.
        """
        now = datetime.datetime.now()
        if not force and not self.is_working_hours(now):
            logging.info("[tasks_watcher] Fuera de horario laboral. Recordatorios pausados.")
            return 0

        tasks = self.fetch_pending_tasks()
        if not tasks:
            logging.info("[tasks_watcher] No hay tareas pendientes en este momento.")
            return 0

        notifications_sent = 0
        current_time = time.time()
        min_interval_seconds = MIN_REMINDER_INTERVAL_HOURS * 3600

        for task in tasks:
            task_id = str(task.get("id"))
            contact = task.get("assignee_contact") or {}
            chat_id = contact.get("telegram_chat_id")

            # Solo notificar si el empleado tiene su chat_id de Telegram vinculado
            if not chat_id:
                continue

            last_sent = self.reminders_state.get(task_id, 0)
            if not force and (current_time - last_sent < min_interval_seconds):
                # Todavía no ha pasado el intervalo mínimo para esta tarea
                continue

            # Enviar mensaje con botones interactivos
            text = self.format_task_message(task)
            keyboard = self.generate_task_keyboard(task_id)
            res = self.send_telegram_message(chat_id, text, reply_markup=keyboard)

            if res.get("ok"):
                self.reminders_state[task_id] = current_time
                notifications_sent += 1

        if notifications_sent > 0:
            self._save_state()

        logging.info(f"[tasks_watcher] Verificación completada: {notifications_sent} recordatorios enviados.")
        return notifications_sent

    def handle_callback_query(self, callback_query: dict) -> bool:
        """
        Maneja los clics en los botones interactivos ('ts:<task_id>:<new_status>').
        """
        cq_id = callback_query.get("id")
        data = callback_query.get("data", "")
        from_user = callback_query.get("from", {})
        chat_id = callback_query.get("message", {}).get("chat", {}).get("id")
        user_name = from_user.get("first_name") or from_user.get("username") or "Empleado"

        if not data.startswith("ts:"):
            return False

        parts = data.split(":")
        if len(parts) < 3:
            self.answer_callback_query(cq_id, text="Datos de botón inválidos", show_alert=True)
            return True

        _, task_id, new_status = parts
        res = self.update_task_status(
            task_id=task_id,
            new_status=new_status,
            author_name=user_name,
            note=f"Estado cambiado a '{new_status}' por {user_name} vía Telegram",
        )

        if res.get("success"):
            task_info = res.get("task", {})
            task_title = task_info.get("title", "Tarea")
            task_code = task_info.get("task_code", "")

            self.answer_callback_query(cq_id, text=f"✅ Estado actualizado a: {new_status}")
            if chat_id:
                self.send_telegram_message(
                    chat_id,
                    f"✅ <b>[{task_code}] {task_title}</b> actualizada correctamente a: <b>{new_status}</b> por {user_name}.",
                )
        else:
            err = res.get("error", "Error al actualizar")
            self.answer_callback_query(cq_id, text=f"⚠️ {err}", show_alert=True)

        return True
