from flask import Flask, request, session, render_template, redirect, url_for, abort
from flask import current_app, g
from flask.cli import with_appcontext

import configparser
import functools
import glob
import itertools
import os.path
import secrets
import sqlite3
import sys
import textwrap
import uuid

import click


class DefaultConfig:
    DEBUG = False
    DATABASE = "./app.db"
    PEER_JS = {"host": "localhost", "port": 9000}
    HEARTBEAT_MS = 15000
    ONLINE_STATUS_EXPIRES = "30 seconds"


app = Flask("gotchufam", instance_relative_config=True)
app.config.from_object(DefaultConfig())
if not os.environ.get("GOTCHUFAM_UNCONFIGURED"):
    app.config.from_pyfile("gotchufam.ini")


class Row(sqlite3.Row):
    def __getattr__(self, name):
        return self[name]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = Row

    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


app.teardown_appcontext(close_db)


@app.cli.command("init-db")
@with_appcontext
def init_db_command():
    db = get_db()
    for statement in schema():
        print(statement)
        db.executescript(statement)
    click.echo("Initialized the database.")


@app.cli.command("init-config")
@click.argument("config_file")
def init_config_command(config_file):
    with open(config_file, "wt") as fd:
        fd.write("# vim: filetype=python\n")
        fd.write(f"SECRET_KEY = {repr(secrets.token_bytes(32))}\n")
        fd.write(f"DATABASE = 'instance/app.db'\n")
        fd.write(f"PEER_JS = {{ 'host': 'penguin.linux.test', 'port': 9000 }}\n")
    click.echo(f"Initialized the config file at {config_file}")


@app.cli.command("add-family")
@click.argument("display_name")
@with_appcontext
def add_family_command(display_name):
    db = get_db()
    login_id = uuid.uuid4()
    db.execute(
        "INSERT INTO family (login_id, display_name) VALUES (?, ?)",
        (str(login_id), display_name),
    )
    db.execute("COMMIT")
    click.echo(f"Added family {display_name!r}: /login?family={login_id}")
    click.echo(url_for(".login", family=login_id))


@app.cli.command("list-families")
@with_appcontext
def list_family_command():
    db = get_db()
    for family in list(db.execute("SELECT display_name, login_id FROM family")):
        click.echo(f"{family.display_name!r}: /login?family={family.login_id}")


def schema():
    return textwrap.dedent(
        """
    CREATE TABLE family (
        id INTEGER PRIMARY KEY,
        login_id TEXT UNIQUE NOT NULL,
        display_name TEXt NOT NULL
    );

    INSERT INTO family (id, login_id, display_name)
    VALUES (1, '0e2ceb8d-a286-4616-b07a-684537b84a1e', 'Test Family');

    CREATE TABLE user (
        id INTEGER PRIMARY KEY,
        family_id INTEGER NOT NULL REFERENCES family(id) ON DELETE RESTRICT, 
        display_name TEXT NOT NULL,
        face_icon BLOB,
        created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires TIMESTAMP NOT NULL
    );
    CREATE INDEX idx_user_expiration ON user(expires, id);
    CREATE UNIQUE INDEX idx_user_name ON user(display_name, family_id);

    CREATE TABLE user_online (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        client_id TEXT UNIQUE NOT NULL,
        created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        expires TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES user (id) ON DELETE CASCADE
    );

    CREATE INDEX idx_user_online_expiration ON user_online(expires, id);
    """
    ).split(";")


def query_online(family_id):
    return get_db().execute(
        "SELECT display_name, user_id, client_id FROM user_online JOIN user WHERE user_online.expires > datetime('now') AND family_id = ?",
        (family_id,),
    )


def query_family(family_id):
    return get_db().execute(
        "SELECT display_name, face_icon FROM user WHERE family_id = ?", (family_id,)
    )


def query_user_heartbeat(user_id):
    get_db().execute(
        "UPDATE user SET expires = datetime(datetime('now'), '90 days') WHERE id = ?",
        (user_id,),
    )


def query_online_heartbeat(user_id, client_id):
    get_db().execute(
        "UPDATE user_online expires = datetime(datetime('now'), '90 days') WHERE user_id = ? AND client_id = ?",
        (user_id, client_id),
    )


def ui_require_logged_in():
    def _decorator(func):
        @functools.wraps(func)
        def _ui_require_logged_in(*args, **kwargs):
            db = get_db()
            user_id = session.get("id", None)
            if not user_id:
                return redirect(url_for(".login", dest=request.url))
            else:
                user_id = session.get("id", None)
                user = db.execute(
                    "SELECT id, family_id, display_name FROM user WHERE id = ?",
                    (user_id,),
                ).fetchone()
                if not user:
                    return redirect(url_for(".login", dest=request.url))
            return func(user, *args, **kwargs)

        return _ui_require_logged_in

    return _decorator


def api_require_logged_in():
    def _decorator(func):
        @functools.wraps(func)
        def _api_require_logged_in(*args, **kwargs):
            db = get_db()
            user_id = session.get("id", None)
            user = list(
                db.execute(
                    "SELECT id, family_id, display_name FROM user WHERE id = ?",
                    (user_id,),
                )
            )
            if not user:
                return {"status": "err", "error_id": "loggedout"}
            return func(user[0], *args, **kwargs)

        return _api_require_logged_in

    return _decorator


@app.route("/api/v1/")
def apiv1():
    return ""


def standard_template_args():
    return dict(
        api_root=url_for(".apiv1"),
        peerjs_config=current_app.config["PEER_JS"],
        app_config=dict(HEARTBEAT_MS=current_app.config["HEARTBEAT_MS"],),
    )


@app.route("/home")
def home():
    return render_template("gotchufam.html")


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.ico")


@app.route("/video")
@ui_require_logged_in()
def video(user):
    return render_template("video.html", **standard_template_args())


@app.route("/whoami")
@ui_require_logged_in()
def whoami(user):
    family = (
        get_db()
        .execute("SELECT id, display_name FROM family WHERE id = ?", (user.family_id,))
        .fetchone()
    )
    return render_template(
        "whoami.html", user=user, family=family, **standard_template_args()
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        family_id = request.args.get("family", None)
        return render_template(
            "login.html", family_id=family_id, **standard_template_args()
        )

    family_login_id = request.form["family-id"]
    display_name = request.form["display-name"]
    db = get_db()
    family_id = list(
        db.execute("SELECT id FROM FAMILY WHERE login_id = ?", (family_login_id,))
    )
    if family_id:
        family_id = family_id[0].id
    else:
        family_id = None
    db.execute(
        "INSERT INTO user (display_name, family_id, expires) "
        "VALUES (?, ?, datetime(datetime('now'), ?)) "
        "ON CONFLICT (display_name, family_id) DO UPDATE SET expires = excluded.expires",
        (display_name, family_id, app.config["ONLINE_STATUS_EXPIRES"]),
    )

    user = db.execute(
        "SELECT id FROM user WHERE display_name = ? AND family_id = ?",
        (display_name, family_id),
    ).fetchone()
    session["id"] = user.id
    dest = request.args.get("next", None)
    if not dest:
        dest = url_for(".video")
    db.execute("COMMIT")
    return redirect(dest)


@app.route("/logout")
@ui_require_logged_in()
def logout_page(user):
    user_id = session.pop("id", None)
    return redirect(url_for(".login"))


@app.route("/api/v1/logout")
def logout_api():
    db = get_db()
    user_id = session.pop("id", None)
    client_id = request.args.get("client_id", None)
    if client_id is not None and user_id is not None:
        db.execute(
            "DELETE FROM user_online WHERE client_id = ? AND user_id = ?",
            (client_id, user_id),
        )
    return {"status": "ok"}


@app.route("/api/v1/whoswho")
@api_require_logged_in()
def whoswho(user):
    return {
        "status": "ok",
        "family": [
            {"display_name": u.display_name, "face_icon": u.face_icon}
            for u in query_family(user.family_id)
        ],
    }


@app.route("/api/v1/heartbeat", methods=["POST"])
@api_require_logged_in()
def heartbeat(user):
    db = get_db()
    client_id = request.form["client_id"]
    if client_id == "null" or not client_id:
        app.logger.error("Client id for %s is %s", user.display_name, client_id)
        abort(400)

    db.execute(
        "INSERT INTO user_online (user_id, client_id, expires) VALUES (?, ?, datetime(datetime('now'), ?)) ON CONFLICT (client_id) DO UPDATE SET expires = excluded.expires",
        (user.id, client_id, app.config["ONLINE_STATUS_EXPIRES"]),
    )

    query_user_heartbeat(user.id)

    db.execute("DELETE FROM user WHERE expires < datetime('now')")
    db.execute("DELETE FROM user_online WHERE expires < datetime('now')")

    online = [
        {"display_name": u.display_name, "user_id": u.user_id, "client_id": u.client_id}
        for u in query_online(user.family_id)
    ]
    db.execute("COMMIT")
    return {"status": "ok", "online": online}


if __name__ == "__main__":
    app.run(debug=True)
