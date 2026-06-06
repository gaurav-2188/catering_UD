"""add updated_at retention storage branding

Revision ID: cc38d6e8e1f2
Revises: 9a097412b4d9
Create Date: 2026-06-06 10:56:10.047810

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'cc38d6e8e1f2'
down_revision: Union[str, Sequence[str], None] = '9a097412b4d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # NOTE: Do NOT drop bookings_signal here. It's intentionally absent from the
    # SQLAlchemy models (internal pub/sub helper used by Realtime), so autogenerate
    # flags it — we want to keep it.

    # 1) updated_at column + trigger to auto-stamp on every UPDATE
    op.add_column('bookings', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE bookings SET updated_at = COALESCE(updated_at, created_at, NOW())")
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_set_updated_at() RETURNS TRIGGER AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$ LANGUAGE plpgsql;
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_bookings_updated_at ON bookings;")
    op.execute("""
        CREATE TRIGGER trg_bookings_updated_at
        BEFORE UPDATE ON bookings
        FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
    """)

    # 2) Retention cleanup function + pg_cron schedule (idempotent)
    op.execute("""
        CREATE OR REPLACE FUNCTION cleanup_old_bookings() RETURNS void AS $$
        BEGIN
            DELETE FROM bookings WHERE status='completed' AND updated_at < NOW() - INTERVAL '6 months';
            DELETE FROM bookings WHERE status='cancelled' AND updated_at < NOW() - INTERVAL '3 months';
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE EXTENSION IF NOT EXISTS pg_cron;
            -- Unschedule any prior copy with the same name
            PERFORM cron.unschedule(jobid)
              FROM cron.job WHERE jobname = 'ud_catering_cleanup_old_bookings';
            PERFORM cron.schedule(
                'ud_catering_cleanup_old_bookings',
                '0 2 * * *',
                $job$ SELECT cleanup_old_bookings(); $job$
            );
        EXCEPTION WHEN OTHERS THEN
            -- pg_cron may not be available in some environments; the cleanup
            -- function is still callable from the backend on a schedule.
            RAISE NOTICE 'pg_cron schedule skipped: %', SQLERRM;
        END $$;
    """)

    # 3) Public 'branding' storage bucket + read/write policies
    op.execute("INSERT INTO storage.buckets (id, name, public) VALUES ('branding','branding', true) ON CONFLICT (id) DO NOTHING;")
    op.execute("DROP POLICY IF EXISTS branding_public_read ON storage.objects;")
    op.execute("CREATE POLICY branding_public_read ON storage.objects FOR SELECT TO public USING (bucket_id = 'branding');")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS branding_public_read ON storage.objects;")
    op.execute("DELETE FROM storage.buckets WHERE id = 'branding';")
    op.execute("""
        DO $$ BEGIN
            PERFORM cron.unschedule(jobid) FROM cron.job WHERE jobname = 'ud_catering_cleanup_old_bookings';
        EXCEPTION WHEN OTHERS THEN NULL; END $$;
    """)
    op.execute("DROP FUNCTION IF EXISTS cleanup_old_bookings();")
    op.execute("DROP TRIGGER IF EXISTS trg_bookings_updated_at ON bookings;")
    op.execute("DROP FUNCTION IF EXISTS fn_set_updated_at();")
    op.drop_column('bookings', 'updated_at')
