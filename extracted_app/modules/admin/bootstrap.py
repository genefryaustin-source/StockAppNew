from __future__ import annotations

import hashlib
import uuid

import streamlit as st
from sqlalchemy import text


def _get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default))
    except Exception:
        return default


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def bootstrap_super_admin(db) -> None:
    user_count = db.execute(
        text("SELECT COUNT(*) FROM users")
    ).scalar()

    if user_count and int(user_count) > 0:
        print("[bootstrap] Users exist. Skipping super admin bootstrap.")
        return

    email = _get_secret("SUPER_ADMIN_EMAIL", "admin@test.com")
    password = _get_secret("SUPER_ADMIN_PASSWORD", "password")

    if not email or not password:
        raise RuntimeError("SUPER_ADMIN_EMAIL and SUPER_ADMIN_PASSWORD are required.")

    db.execute(
        text("""
        INSERT OR IGNORE INTO tenants (
            id,
            name,
            created_at,
            is_active
        )
        VALUES (
            'default_tenant',
            'Default Tenant',
            CURRENT_TIMESTAMP,
            1
        )
        """)
    )

    db.execute(
        text("""
        INSERT INTO users (
            id,
            tenant_id,
            email,
            role,
            created_at,
            password_hash,
            is_active,
            updated_at
        )
        VALUES (
            :id,
            'default_tenant',
            :email,
            'super_admin',
            CURRENT_TIMESTAMP,
            :password_hash,
            1,
            CURRENT_TIMESTAMP
        )
        """),
        {
            "id": str(uuid.uuid4()),
            "email": email.strip().lower(),
            "password_hash": _hash_password(password),
        },
    )

    db.commit()

    print(f"[bootstrap] Created super admin: {email}")