"""
app.py — Real-Time Chat Application Backend
============================================
Built with Flask + Flask-SocketIO + SQLite.

Architecture overview:
  - Flask handles HTTP routes (pages, auth redirects).
  - Flask-SocketIO handles the persistent WebSocket connections
    that power real-time messaging and presence updates.
  - SQLite stores users, messages per room, and room memberships.
  - Werkzeug's password hashing keeps credentials secure at rest.

Typical request flow:
  1. User visits "/" → redirected to /login if not authenticated.
  2. User registers at /register → password hashed → stored in DB.
  3. User logs in at /login → session opened → redirected to "/".
  4. Client JS opens a Socket.IO connection and emits 'join' for a room.
  5. Messages flow via 'send_message' / 'receive_message' events.
  6. Disconnect / leave events update the online-users tracker.
"""


from flask import Flask, render_template, request, redirect, url_for, session
from flask_socketio import SocketIO, send, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3




# ---------------------------------------------------------------------------
# App & SocketIO initialisation
# ---------------------------------------------------------------------------

app = Flask(__name__)

# SECRET_KEY signs the session cookie — change this to a long random value
# in production (e.g. generated with: python -c "import secrets; print(secrets.token_hex(32))")
app.config['SECRET_KEY'] = 'une_cle_secrete_tres_complexe_et_longue_12345!'

socketio = SocketIO(app, cors_allowed_origins="*")

# ---------------------------------------------------------------------------
# In-memory presence tracker
# ---------------------------------------------------------------------------

# Maps Socket.IO session ID (request.sid) → { 'username': str, 'room': str }
# This lets us instantly know which room a socket belongs to when it disconnects,
# without hitting the database on every event.
online_users = {}


# ===========================================================================
# 1. DATABASE INITIALISATION
# ===========================================================================

def init_db():
    """
    Create the SQLite database and all required tables if they do not
    already exist.  Called once at startup.

    Tables:
      users        — registered accounts (email, username, hashed password)
      messages     — all chat messages, tied to a room
      room_members — persistent membership list for each room
    """
    conn = sqlite3.connect("chat.db")
    cursor = conn.cursor()

    # --- Users table ---
    # 'email' and 'username' both carry a UNIQUE constraint so the DB itself
    # enforces no duplicate accounts (caught as IntegrityError in /register).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            email    TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # --- Messages table ---
    # 'room' links a message to the correct chat room.
    # 'timestamp' defaults to the current UTC time so we can replay history
    # in chronological order.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            room      TEXT,
            username  TEXT,
            message   TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --- Room members table ---
    # Stores which users have ever joined a room (persistent membership).
    # This is separate from the in-memory 'online_users' dict which only
    # tracks who is currently connected.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS room_members (
            room     TEXT,
            username TEXT
        )
    """)

    conn.commit()
    conn.close()


# Run once at import / startup time.
init_db()


# ===========================================================================
# 2. AUTHENTICATION ROUTES
# ===========================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    GET  → render the registration form (register.html).
    POST → validate input, hash password, insert new user, redirect to login.

    On duplicate email or username the DB raises IntegrityError, which we
    catch and surface as a simple error message.
    """
    if request.method == 'POST':
        email    = request.form['email']
        username = request.form['username']
        password = request.form['password']

        # Hash the password with Werkzeug (bcrypt-based PBKDF2 by default).
        # Never store plain-text passwords.
        hashed_password = generate_password_hash(password)

        conn   = sqlite3.connect("chat.db")
        cursor = conn.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (email, username, password) VALUES (?, ?, ?)",
                (email, username, hashed_password)
            )
            conn.commit()
            conn.close()
            # Registration successful — send the user to the login page.
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            # The UNIQUE constraint on email or username was violated.
            conn.close()
            return (
                "Error: That email or username is already taken. "
                "<a href='/register'>Try again</a>"
            )

    # GET request — just show the registration form.
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    GET  → render the login form (login.html).
    POST → look up the user by email, verify the password hash, open session.

    Column indices for the 'users' row:
      user[0] = id  |  user[1] = email  |  user[2] = username  |  user[3] = password
    """
    if request.method == 'POST':
        email            = request.form['email']
        attempted_password = request.form['password']

        conn   = sqlite3.connect("chat.db")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        # check_password_hash compares the attempted password against the
        # stored hash without ever reversing it.
        if user and check_password_hash(user[3], attempted_password):
            # Credentials are valid — store user info in the signed session cookie.
            session['user_id'] = user[0]
            session['username'] = user[2]
            return redirect(url_for('accueil'))
        else:
            return (
                "Error: Incorrect email or password. "
                "<a href='/login'>Try again</a>"
            )

    # GET request — show the login form.
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    Clear the session (effectively logging the user out) and redirect to login.
    Using .pop() with a default of None avoids a KeyError if the key is missing.
    """
    session.pop('user_id', None)
    session.pop('username', None)
    return redirect(url_for('login'))


# ===========================================================================
# 3. MAIN PROTECTED ROUTE
# ===========================================================================

@app.route('/')
def accueil():
    """
    The main chat page.

    Access control: if the user is not logged in (no 'username' in session),
    redirect them to /login.  This is a simple session-based guard — for
    larger apps consider a decorator (e.g. @login_required from Flask-Login).

    We pass the logged-in username to the template so the JavaScript layer
    can use it to label outgoing messages and style its own bubbles differently.
    """
    if 'username' not in session:
        return redirect(url_for('login'))

    # Load ALL messages for the initial page render.
    # Note: room-specific history is reloaded via Socket.IO on 'join',
    # so this query is mostly kept for completeness / debugging.
    conn   = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, message, timestamp FROM messages ORDER BY timestamp ASC"
    )
    messages = cursor.fetchall()
    conn.close()

    return render_template('index.html', messages=messages, username=session['username'])


# ===========================================================================
# 4. SOCKET.IO EVENT HANDLERS
# ===========================================================================

@socketio.on('send_message')
def handle_message(data):
    """
    Fired by the client when the user sends a chat message.

    Expected payload:
      { room: str, username: str, message: str }

    Steps:
      1. Persist the message to the database.
      2. Broadcast it to every socket in the same room (including the sender)
         via the 'receive_message' event.
    """
    # Persist the message so it appears in history for future joins.
    conn   = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (room, username, message) VALUES (?, ?, ?)",
        (data['room'], data['username'], data['message'])
    )
    conn.commit()
    conn.close()

    print(f"[MSG] {data['username']} → {data['room']}: {data['message']}")

    # Emit only to clients in this specific room, not to the whole server.
    emit("receive_message", data, to=data['room'])


@socketio.on('join')
def on_join(data):
    """
    Fired when a client wants to enter a chat room.

    Expected payload:
      { username: str, room: str }

    Steps:
      1. Add the socket to the Socket.IO room (required for targeted broadcasts).
      2. Register this socket in the online_users tracker.
      3. Announce the join to the room.
      4. Compute the de-duplicated online list (same user, multiple tabs → counted once).
      5. Fetch the persistent member list from the DB.
      6. Push both lists to the room via 'maj_utilisateurs'.
      7. Load and emit this room's message history to the joining socket only.
    """
    username = data['username']
    room     = data['room']

    # Step 1 — join the Socket.IO room so this socket receives targeted emits.
    join_room(room)

    # Step 2 — track this socket in the presence dict.
    online_users[request.sid] = {'username': username, 'room': room}

    # Step 3 — notify everyone in the room.
    emit('system_message', f"{username} joined the room", to=room)

    # Step 4 — de-duplicate: a user with three open tabs counts as one.
    unique_online = list(set([
        u['username'] for u in online_users.values() if u['room'] == room
    ]))

    # Step 5 — fetch registered/persistent members from the DB.
    conn   = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM room_members WHERE room = ?", (room,))
    registered_members = [row[0] for row in cursor.fetchall()]
    conn.close()

    # Step 6 — push the updated member lists to everyone in the room.
    emit('maj_utilisateurs', {'en_ligne': unique_online, 'inscrits': registered_members}, to=room)

    # Step 7 — send this room's message history to the joining client only.
    # (No 'to=' argument means the emit goes only to the current socket.)
    conn   = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, message FROM messages WHERE room = ? ORDER BY timestamp ASC",
        (room,)
    )
    history = cursor.fetchall()
    conn.close()

    emit('charger_historique', history)


@socketio.on('quitter_salon')
def on_leave(data):
    """
    Fired when the user explicitly clicks the 'Leave room' button.

    Expected payload:
      { room: str, username: str }

    Steps:
      1. Remove the socket from the Socket.IO room.
      2. Remove this socket from the online_users tracker.
      3. Announce the departure to the remaining members.
      4. Push the updated online/registered lists to those who remain.
    """
    room     = data['room']
    username = data['username']

    # Step 1 — detach from the Socket.IO room.
    leave_room(room)

    # Step 2 — remove from presence tracker.
    if request.sid in online_users:
        del online_users[request.sid]

    # Step 3 — notify the room.
    emit('system_message', f"🚪 {username} left the room", to=room)

    # Step 4 — recompute and broadcast the updated lists.
    unique_online = list(set([
        u['username'] for u in online_users.values() if u['room'] == room
    ]))

    conn   = sqlite3.connect("chat.db")
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM room_members WHERE room = ?", (room,))
    registered_members = [row[0] for row in cursor.fetchall()]
    conn.close()

    emit('maj_utilisateurs', {'en_ligne': unique_online, 'inscrits': registered_members}, to=room)


@socketio.on('disconnect')
def on_disconnect():
    """
    Fired automatically by Socket.IO when a client's connection drops
    (browser tab closed, network loss, etc.).

    This is the fallback for unclean disconnections — the explicit
    'quitter_salon' handler covers intentional leaves.

    Steps:
      1. Look up the user in the presence tracker using request.sid.
      2. Remove them from the tracker.
      3. Announce the departure to the room.
      4. Push the updated lists to remaining members.
    """
    user_info = online_users.get(request.sid)

    if user_info:
        username = user_info['username']
        room     = user_info['room']

        # Step 2 — clean up presence tracker.
        del online_users[request.sid]

        # Step 3 — notify the room of the departure.
        socketio.emit('system_message', f"{username} left the room", to=room)

        # Step 4 — recompute and broadcast updated lists.
        unique_online = list(set([
            u['username'] for u in online_users.values() if u['room'] == room
        ]))

        conn   = sqlite3.connect("chat.db")
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM room_members WHERE room = ?", (room,))
        registered_members = [row[0] for row in cursor.fetchall()]
        conn.close()

        emit('maj_utilisateurs', {'en_ligne': unique_online, 'inscrits': registered_members}, to=room)


# ===========================================================================
# 5. ENTRY POINT
# ===========================================================================

if __name__ == '__main__':
    # debug=True enables:
    #   • Auto-reload on code changes (no need to restart manually).
    #   • Detailed error pages in the browser.
    # NEVER run with debug=True in production.
    socketio.run(app, debug=True, port=5000)