from django.db import migrations


def _get_columns(connection, table_name):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
    return {column.name for column in description}


def _get_column_metadata(connection, table_name, column_name):
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT data_type, udt_name, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = %s
              AND column_name = %s
            """,
            [table_name, column_name],
        )
        row = cursor.fetchone()

    if not row:
        return None

    return {
        "data_type": row[0],
        "udt_name": row[1],
        "max_length": row[2],
    }


def sync_legacy_risk_schema(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    risk_columns = _get_columns(connection, "app_risk")

    if "is_active" not in risk_columns:
        schema_editor.execute(
            "ALTER TABLE app_risk ADD COLUMN is_active boolean NOT NULL DEFAULT TRUE"
        )

    if "risk_manager" not in risk_columns:
        schema_editor.execute(
            "ALTER TABLE app_risk ADD COLUMN risk_manager varchar(250) NULL"
        )

    if "risk_derector" not in risk_columns:
        schema_editor.execute(
            "ALTER TABLE app_risk ADD COLUMN risk_derector varchar(250) NULL"
        )

    if "Impact" not in risk_columns:
        schema_editor.execute(
            'ALTER TABLE app_risk ADD COLUMN "Impact" varchar(500) NULL'
        )

    if "possible_loss" not in risk_columns:
        schema_editor.execute(
            "ALTER TABLE app_risk ADD COLUMN possible_loss double precision NOT NULL DEFAULT 0"
        )
        if "expected_loss" in risk_columns:
            schema_editor.execute(
                """
                UPDATE app_risk
                SET possible_loss = COALESCE(expected_loss, 0)
                WHERE possible_loss = 0
                """
            )

    if "responsible_department_id_id" not in risk_columns:
        schema_editor.execute(
            "ALTER TABLE app_risk ADD COLUMN responsible_department_id_id bigint NULL"
        )
        if "department_id" in risk_columns:
            schema_editor.execute(
                """
                UPDATE app_risk
                SET responsible_department_id_id = department_id
                WHERE responsible_department_id_id IS NULL
                """
            )
        schema_editor.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'app_risk_responsible_department_fk'
                ) THEN
                    ALTER TABLE app_risk
                    ADD CONSTRAINT app_risk_responsible_department_fk
                    FOREIGN KEY (responsible_department_id_id)
                    REFERENCES app_department (id)
                    DEFERRABLE INITIALLY DEFERRED;
                END IF;
            END $$;
            """
        )
        schema_editor.execute(
            """
            CREATE INDEX IF NOT EXISTS app_risk_responsible_department_id_idx
            ON app_risk (responsible_department_id_id)
            """
        )

    probability_metadata = _get_column_metadata(connection, "app_risk", "probability")
    if probability_metadata:
        if probability_metadata["udt_name"] in {"float4", "float8", "numeric"}:
            schema_editor.execute(
                """
                ALTER TABLE app_risk
                ALTER COLUMN probability TYPE varchar(500)
                USING CASE
                    WHEN probability IS NULL THEN NULL
                    WHEN probability >= 0.67 THEN 'HIGH'
                    WHEN probability >= 0.34 THEN 'MEDIUM'
                    ELSE 'LOW'
                END
                """
            )
        elif (
            probability_metadata["data_type"] == "character varying"
            and probability_metadata["max_length"]
            and probability_metadata["max_length"] < 500
        ):
            schema_editor.execute(
                "ALTER TABLE app_risk ALTER COLUMN probability TYPE varchar(500)"
            )

    status_metadata = _get_column_metadata(connection, "app_risk", "status")
    if (
        status_metadata
        and status_metadata["data_type"] == "character varying"
        and status_metadata["max_length"]
        and status_metadata["max_length"] < 2000
    ):
        schema_editor.execute(
            "ALTER TABLE app_risk ALTER COLUMN status TYPE varchar(2000)"
        )


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(sync_legacy_risk_schema, migrations.RunPython.noop),
    ]
