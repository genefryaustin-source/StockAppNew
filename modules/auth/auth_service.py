import hashlib
import uuid
from datetime import datetime, UTC
from sqlalchemy import text


SESSION_TIMEOUT_MINUTES = 30


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def authenticate(db, email, password):
    user = db.execute(text("""
        SELECT *
        FROM users
        WHERE lower(trim(email)) = :email
          AND COALESCE(is_active, 1) = 1
        LIMIT 1
    """), {"email": email.lower().strip()}).fetchone()

    # print("DEBUG LOGIN EMAIL:", email)

    if not user:
        print("DEBUG LOGIN FAIL: user not found or inactive")
        return None

    input_hash = hash_password(password)
    stored_hash = user.password_hash

    #print("DEBUG INPUT PASSWORD:", password)
    #print("DEBUG INPUT HASH:", input_hash)
    #print("DEBUG STORED HASH:", stored_hash)

    if not stored_hash:
        print("DEBUG LOGIN FAIL: stored hash missing")
        return None

    if stored_hash != input_hash:
        print("DEBUG LOGIN FAIL: hash mismatch")
        return None

    #print("DEBUG LOGIN SUCCESS")

    return {

        "user_id": str(user.id),
        "tenant_id": getattr(user, "tenant_id", None),
        "role": user.role,
        "email": user.email,
        "is_active": getattr(user, "is_active", 1),
        "last_login_at": datetime.now(UTC).isoformat(),
    }


def create_user(db, email, password, role, tenant_id=None, is_active: int = 1):
    db.execute(text("""
        INSERT INTO users (
            id,
            email,
            password_hash,
            role,
            tenant_id,
            is_active
        )
        VALUES (
            :id,
            :email,
            :pw,
            :role,
            :tenant,
            :is_active
        )
    """), {
        "id": str(uuid.uuid4()),
        "email": email.lower().strip(),
        "pw": hash_password(password),
        "role": role,
        "tenant": tenant_id,
        "is_active": int(is_active),
    })
    db.commit()


def list_users_for_scope(db, current_user: dict):
    role = current_user.get("role")
    tenant_id = current_user.get("tenant_id")

    if role == "super_admin":
        rows = db.execute(text("""
            SELECT id, email, role, tenant_id, COALESCE(is_active, 1) AS is_active, created_at
            FROM users
            ORDER BY created_at DESC, email ASC
        """)).fetchall()
    elif role == "tenant_admin":
        rows = db.execute(text("""
            SELECT id, email, role, tenant_id, COALESCE(is_active, 1) AS is_active, created_at
            FROM users
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC, email ASC
        """), {"tenant_id": tenant_id}).fetchall()
    else:
        rows = []

    return rows


def get_user_by_id(db, user_id: str):
    row = db.execute(text("""
        SELECT id, email, role, tenant_id, COALESCE(is_active, 1) AS is_active, created_at
        FROM users
        WHERE id = :user_id
        LIMIT 1
    """), {"user_id": user_id}).fetchone()
    return row


def update_user(db, target_user_id: str, email: str, role: str, tenant_id=None):
    db.execute(text("""
        UPDATE users
        SET email = :email,
            role = :role,
            tenant_id = :tenant_id
        WHERE id = :user_id
    """), {
        "email": email.lower().strip(),
        "role": role,
        "tenant_id": tenant_id,
        "user_id": target_user_id,
    })
    db.commit()


def set_user_active(db, target_user_id: str, is_active: bool):
    db.execute(text("""
        UPDATE users
        SET is_active = :is_active
        WHERE id = :user_id
    """), {
        "is_active": 1 if is_active else 0,
        "user_id": target_user_id,
    })
    db.commit()


def reset_user_password(db, target_user_id: str, new_password: str):
    db.execute(text("""
        UPDATE users
        SET password_hash = :password_hash
        WHERE id = :user_id
    """), {
        "password_hash": hash_password(new_password),
        "user_id": target_user_id,
    })
    db.commit()


def delete_user(db, target_user_id: str):
    db.execute(text("""
        DELETE FROM users
        WHERE id = :user_id
    """), {"user_id": target_user_id})
    db.commit()


def logout():
    keys_to_clear = ["user", "last_activity_ts"]
    for key in keys_to_clear:
        if key in __import__("streamlit").session_state:
            del __import__("streamlit").session_state[key]