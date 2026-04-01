from django.db import migrations


def _table_names(connection):
    return set(connection.introspection.table_names())


def _get_columns(connection, table_name):
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table_name)
    return {column.name for column in description}


def _add_fk_constraint(schema_editor, table_name, column_name, target_table, constraint_name):
    schema_editor.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = '{constraint_name}'
            ) THEN
                ALTER TABLE {table_name}
                ADD CONSTRAINT {constraint_name}
                FOREIGN KEY ({column_name})
                REFERENCES {target_table} (id)
                DEFERRABLE INITIALLY DEFERRED;
            END IF;
        END $$;
        """
    )


def sync_legacy_workflow_schema(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    tables = _table_names(connection)

    if "app_riskdecition" not in tables:
        if "app_riskdecision" in tables:
            schema_editor.execute("ALTER TABLE app_riskdecision RENAME TO app_riskdecition")
        else:
            schema_editor.create_model(apps.get_model("app", "RiskDecition"))
        tables = _table_names(connection)

    if "app_mitigation" in tables:
        mitigation_columns = _get_columns(connection, "app_mitigation")
        if "department_director" not in mitigation_columns:
            schema_editor.execute(
                "ALTER TABLE app_mitigation ADD COLUMN department_director varchar(500) NOT NULL DEFAULT ''"
            )

    if "app_riskdecition" in tables:
        risk_decition_columns = _get_columns(connection, "app_riskdecition")
        if "decision_type" in risk_decition_columns and "decition_type" not in risk_decition_columns:
            schema_editor.execute(
                "ALTER TABLE app_riskdecition RENAME COLUMN decision_type TO decition_type"
            )

    if "app_riskcommittee" in tables:
        committee_columns = _get_columns(connection, "app_riskcommittee")

        if "last_decision" in committee_columns and "last_decition" not in committee_columns:
            schema_editor.execute(
                "ALTER TABLE app_riskcommittee RENAME COLUMN last_decision TO last_decition"
            )
            committee_columns = _get_columns(connection, "app_riskcommittee")

        if "last_decision_at" in committee_columns and "last_decition_at" not in committee_columns:
            schema_editor.execute(
                "ALTER TABLE app_riskcommittee RENAME COLUMN last_decision_at TO last_decition_at"
            )
            committee_columns = _get_columns(connection, "app_riskcommittee")

        if "last_decition" not in committee_columns:
            schema_editor.execute(
                "ALTER TABLE app_riskcommittee ADD COLUMN last_decition text NOT NULL DEFAULT ''"
            )

        if "last_decition_at" not in committee_columns:
            schema_editor.execute(
                "ALTER TABLE app_riskcommittee ADD COLUMN last_decition_at timestamp with time zone NULL"
            )

        if "decision_id" not in committee_columns:
            schema_editor.execute(
                "ALTER TABLE app_riskcommittee ADD COLUMN decision_id bigint NULL"
            )
            schema_editor.execute(
                """
                CREATE INDEX IF NOT EXISTS app_riskcommittee_decision_id_idx
                ON app_riskcommittee (decision_id)
                """
            )
            _add_fk_constraint(
                schema_editor,
                "app_riskcommittee",
                "decision_id",
                "app_riskdecition",
                "app_riskcommittee_decision_fk",
            )

        if "mitigation_id" not in committee_columns:
            schema_editor.execute(
                "ALTER TABLE app_riskcommittee ADD COLUMN mitigation_id bigint NULL"
            )
            schema_editor.execute(
                """
                CREATE INDEX IF NOT EXISTS app_riskcommittee_mitigation_id_idx
                ON app_riskcommittee (mitigation_id)
                """
            )
            _add_fk_constraint(
                schema_editor,
                "app_riskcommittee",
                "mitigation_id",
                "app_mitigation",
                "app_riskcommittee_mitigation_fk",
            )
    else:
        schema_editor.create_model(apps.get_model("app", "RiskCommittee"))

    if "app_riskactivityrecipient" not in tables:
        schema_editor.create_model(apps.get_model("app", "RiskActivityRecipient"))

    if "app_replyriskactivity" not in tables:
        schema_editor.create_model(apps.get_model("app", "ReplyRiskActivity"))

    if "app_notification" not in tables:
        schema_editor.create_model(apps.get_model("app", "Notification"))


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("app", "0002_sync_legacy_risk_schema"),
    ]

    operations = [
        migrations.RunPython(sync_legacy_workflow_schema, migrations.RunPython.noop),
    ]
