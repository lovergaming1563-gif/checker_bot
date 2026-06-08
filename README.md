# checker-bot

A Telegram-based request routing and gateway system built with **Aiogram 3.x**, **SQLAlchemy 2.0**, and **SQLite**.

## 🚀 Overview

The **checker-bot** acts as a middleman between users and service-specific Telegram groups. Users submit requests (mobile numbers), which are then routed to configured groups for processing. The bot monitors these groups for results and relays them back to the original user.

## 🛠 Features

- **Dynamic Services:** Admins can manage services (add/edit/delete/toggle) via a built-in panel.
- **Request Routing:** Automatic forwarding of requests to Telegram groups based on service configuration.
- **Result Matching:** Robust matching logic using group ID and mobile number extraction.
- **Admin Dashboard:** Real-time stats, user moderation (banning), and system monitoring.
- **Broadcast System:** Send mass messages to all registered users with tracking.
- **Monitoring & Alerts:** Uptime tracking, health checks, and proactive admin alerts for critical events.

## 📋 Prerequisites

- Python 3.12+
- A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- At least one administrator Telegram ID.

## ⚙️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd checker-bot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   - Copy `.env.example` to `.env`.
   - Fill in `BOT_TOKEN` and `ADMIN_IDS`.

4. **Run the bot:**
   ```bash
   python -m src.main
   ```

## 🏗 Deployment (Render)

This project is configured for deployment as a **Background Worker** on Render.

1. Connect your GitHub repository to Render.
2. The `render.yaml` file will automatically configure the service.
3. **Important:** Ensure you attach a **Persistent Disk** to `/data` to preserve the SQLite database.

## 🛡 Security

- **Strict Admin Access:** All administrative functions are protected by a dedicated middleware.
- **Global Bans:** Banned users are instantly restricted from all bot features.
- **Duplicate Prevention:** System-wide prevention of multiple active requests for the same number/service.

## 👨‍💻 Admin Setup

1. Send `/start` to the bot to register your ID.
2. Ensure your ID is in the `ADMIN_IDS` variable in `.env`.
3. Use `/admin` to access the dashboard and create your first service.

---
Built with ❤️ using Aiogram 3.x
