# 🤖 Telegram GitHub Repository Watcher Bot

> **Bot interactivo de Telegram para monitorear lanzamientos (releases), tags y actualizaciones de repositorios de GitHub en tiempo real.**

---

## 🌟 Características

- 📦 **Soporte Multi-Repositorio:** Monitorea múltiples repositorios públicos y privados de GitHub de manera simultánea.
- 📱 **Control 100% Interactivo:** Agrega, pausa, reactiva o elimina repositorios enviándole comandos directamente al bot en Telegram.
- ⚡ **Ultra Ligero & $0 Costo:** Consume menos de 15MB de RAM y 0.0% de CPU. No requiere base de datos pesada ni dependencias externas (usa librería estándar de Python).
- 🔒 **Seguridad y Privacidad:** Soporta `GITHUB_TOKEN` para acceder a repositorios privados sin exponer datos sensibles.
- 🐳 **Listo para Docker:** Despliegue con un solo comando mediante Docker Compose.

---

## 📱 Comandos del Bot en Telegram

| Comando | Descripción | Ejemplo |
| :--- | :--- | :--- |
| **`/list`** | Muestra todos los repositorios monitoreados y su estado (Activo / Pausado) | `/list` |
| **`/add owner/repo`** | Agrega un nuevo repositorio para recibir alertas | `/add n8n-io/n8n` |
| **`/disable owner/repo`** | Pausa temporalmente las alertas de ese repositorio | `/disable chatwoot/chatwoot` |
| **`/enable owner/repo`** | Reactiva las alertas de un repositorio pausado | `/enable chatwoot/chatwoot` |
| **`/remove owner/repo`** | Elimina definitivamente el repositorio de la lista | `/remove n8n-io/n8n` |
| **`/check`** | Fuerza una verificación manual de todos los repositorios activos | `/check` |
| **`/help`** | Muestra el menú de ayuda y comandos | `/help` |

---

## 🚀 Instalación y Puesta en Marcha

### 1. Clonar el repositorio
```bash
git clone https://github.com/Christian3h/telegram-bot-repositorios.git
cd telegram-bot-repositorios
```

### 2. Configurar variables de entorno
Copia la plantilla de ejemplo y edita tu archivo `.env`:

```bash
cp .env.example .env
```

Configura tus credenciales:
```env
# Token obtenido desde @BotFather
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhI...

# Tu ID de usuario en Telegram (obtenido desde @userinfobot o enviando /start)
TELEGRAM_CHAT_ID=1234567890

# Intervalo de chequeo en segundos (por defecto: 7200 = 2 horas)
CHECK_INTERVAL_SECONDS=7200

# Opcional: GitHub Token clásico con scope 'repo' (para repos privados)
GITHUB_TOKEN=
```

---

### 3. Ejecutar con Docker Compose (Recomendado)

```bash
docker compose up -d
```

Para ver los registros en tiempo real:
```bash
docker compose logs -f
```

---

### 4. Ejecución nativa con Python (Alternativa)

```bash
# Ejecutar en modo escucha continua (Daemon)
python3 bot.py --daemon

# Ejecutar una sola verificación manual
python3 bot.py --check
```

---

## 📄 Licencia

Este proyecto está bajo la Licencia **MIT**. Siéntete libre de utilizarlo, modificarlo y distribuirlo.

Desarrollado con ❤️ por [Christian3h](https://github.com/Christian3h).
