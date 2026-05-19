from sqlalchemy import text
import uuid

class TenantService:

    def __init__(self, db):
        self.db = db

    def list_tenants(self):
        rows = self.db.execute(text("""
            SELECT id, name, is_active, created_at
            FROM tenants
            ORDER BY name
        """)).fetchall()

        return [
            {
                "id": r[0],
                "name": r[1],
                "is_active": r[2],
                "created_at": r[3],
            }
            for r in rows
        ]

    def create_tenant(self, name: str):
        tenant_id = str(uuid.uuid4())

        self.db.execute(text("""
            INSERT INTO tenants (id, name, is_active)
            VALUES (:id, :name, 1)
        """), {
            "id": tenant_id,
            "name": name
        })

        self.db.commit()

        return tenant_id

    def deactivate_tenant(self, tenant_id: str):
        self.db.execute(text("""
            UPDATE tenants
            SET is_active = 0
            WHERE id = :id
        """), {"id": tenant_id})

        self.db.commit()