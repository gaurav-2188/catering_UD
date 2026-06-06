"""add booking start_at end_at and realtime publication

Revision ID: 3e900c505c71
Revises: 9f587cfcbe9b
Create Date: 2026-06-06 09:12:34.380608

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3e900c505c71'
down_revision: Union[str, Sequence[str], None] = '9f587cfcbe9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bookings', sa.Column('start_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bookings', sa.Column('end_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_bookings_end_at'), 'bookings', ['end_at'], unique=False)
    op.create_index(op.f('ix_bookings_start_at'), 'bookings', ['start_at'], unique=False)

    # Backfill from existing event_date + event_time/event_end_time strings.
    # If end <= start, treat end as next day (overnight).
    op.execute("""
        UPDATE bookings SET
            start_at = (event_date || ' ' || event_time)::timestamptz,
            end_at = CASE
                WHEN event_end_time::time <= event_time::time
                THEN ((event_date::date + INTERVAL '1 day') || ' ' || event_end_time)::timestamptz
                ELSE (event_date || ' ' || event_end_time)::timestamptz
            END
        WHERE start_at IS NULL OR end_at IS NULL
    """)

    # Realtime — let multiple staff see live calendar updates.
    # 1) Allow anon SELECT on bookings so the realtime websocket (which runs
    #    under the anon role for clients using the anon key) can stream changes.
    #    This is intentional for an internal staff console.
    op.execute("CREATE POLICY bookings_anon_read ON bookings FOR SELECT TO anon USING (true);")
    # 2) Add bookings to the supabase_realtime publication.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
                BEGIN
                    EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE bookings';
                EXCEPTION WHEN duplicate_object THEN NULL;
                END;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP POLICY IF EXISTS bookings_anon_read ON bookings;")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
                EXECUTE 'ALTER PUBLICATION supabase_realtime DROP TABLE bookings';
            END IF;
        END $$;
    """)
    op.drop_index(op.f('ix_bookings_start_at'), table_name='bookings')
    op.drop_index(op.f('ix_bookings_end_at'), table_name='bookings')
    op.drop_column('bookings', 'end_at')
    op.drop_column('bookings', 'start_at')
