  Real-Time Chat App

A multi-room, real-time chat application built with **Flask**, **Flask-SocketIO**, and **SQLite** — featuring user authentication, live presence tracking, and message history.

> **This is a v1.0 MVP.** The core features are functional and the project is actively developed. Security hardening, architectural improvements, and new features are planned for upcoming releases — see the [Roadmap](#roadmap) below.

---

 Features

- **Authentication** — register and log in with a hashed password (Werkzeug PBKDF2)
- **Multi-room chat** — join any named room; rooms are isolated from each other
- **Real-time messaging** — instant delivery via WebSockets (Socket.IO)
- **Message history** — past messages reload automatically when you join a room
- **Live presence** — see who is currently online vs. registered in each room
- **Multi-tab aware** — the same user across multiple tabs counts as one online user
- **Clean disconnect handling** — the server detects both intentional leaves and dropped connections
- **Polished UI** — responsive, animated glass-morphism interface; works on mobile

---

 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Real-time | Flask-SocketIO (WebSockets) |
| Database | SQLite 3 |
| Auth | Werkzeug password hashing |
| Frontend | Vanilla JS, Socket.IO client, CSS |

---

 Getting Started

    Prerequisites

- Python 3.8 or higher
- pip

 Installation

   bash
 1. Clone the repository
git clone https://github.com/your-username/your-repo-name.git
cd your-repo-name

 2. Install dependencies
pip install -r requirements.txt

 3. Run the development server
python app.py
```

Then open your browser at **http://localhost:5000**.

> The SQLite database (`chat.db`) is created automatically on first run — no setup needed.

 Requirements


flask
flask-socketio
werkzeug


> Generate a pinned `requirements.txt` with: `pip freeze > requirements.txt`

---

 Project Structure


├── app.py              # Flask app, Socket.IO events, auth routes
├── templates/
│   ├── index.html      # Main chat interface (protected)
│   ├── login.html      # Login page
│   └── register.html   # Registration page
├── chat.db             # SQLite database (auto-generated, not committed)
├── requirements.txt    # Python dependencies
└── README.md

---

 Roadmap

This project is a working MVP. The following improvements are planned for future releases.

  Security
- [ ] Move `SECRET_KEY` to an `.env` file (`python-dotenv`)
- [ ] Add server-side input sanitization and length limits
- [ ] Implement rate limiting on login and message endpoints
- [ ] Add room-level access control (private rooms with passwords or invite links)
- [ ] Replace raw error strings with generic user-facing messages

  Architecture
- [ ] Split `app.py` into modules (`routes/`, `events/`, `models/`)
- [ ] Replace `sqlite3` direct calls with SQLAlchemy ORM
- [ ] Add database connection pooling
- [ ] Introduce a `.env` / config file pattern for all environment-specific values

  Features
- [ ] Direct (private) messaging between users
- [ ] User profile pages and avatars
- [ ] Message reactions and editing
- [ ] Typing indicators
- [ ] File / image sharing
- [ ] Room creation with optional password protection

  Quality
- [ ] Unit tests for auth routes and Socket.IO events
- [ ] Error handling (`try/except`) around all database and socket operations
- [ ] Logging (replace `print()` with Python's `logging` module)

  Deployment
- [ ] Switch from SQLite to PostgreSQL for production
- [ ] Replace in-memory presence tracking with Redis (enables multi-worker deployments)
- [ ] Containerise with Docker
- [ ] CI/CD pipeline (GitHub Actions)

---

  Known Limitations (MVP)

These are acknowledged gaps that will be addressed in upcoming versions:

- `SECRET_KEY` is currently hardcoded — **do not deploy this publicly as-is**
- Online presence state is stored in memory and resets on server restart
- SQLite is not suitable for concurrent production workloads
- No rate limiting — the app is not protected against spam or brute force

---

  Contributing

This is a personal learning project, but feedback and suggestions are very welcome. Feel free to open an issue or start a discussion.

---

  Author

Built by a computer engineering student as a first large-scale project — learning in public, one commit at a time.

---

  License

This project is open source and available under the [MIT License](LICENSE).
