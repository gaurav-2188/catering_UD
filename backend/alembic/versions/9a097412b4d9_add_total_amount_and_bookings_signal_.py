"""add total_amount and bookings_signal for privacy realtime

Revision ID: 9a097412b4d9
Revises: 3e900c505c71
Create Date: 2026-06-06 09:55:41.724440

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a097412b4d9'
down_revision: Union[str, Sequence[str], None] = '3e900c505c71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('bookings', sa.Column('total_amount', sa.Numeric(), server_default='0', nullable=True))

    # Backfill total_amount using per-person pricing: subtotal = sum(item.price) * num_people
    op.execute("""
        WITH per_booking AS (
            SELECT
                b.id,
                COALESCE(SUM((item.value->>'price')::numeric), 0) * b.num_people AS subtotal,
                b.discount_amount AS d_amt,
                b.discount_percent AS d_pct,
                b.gst_percent AS gst_pct,
                b.transportation_cost AS transport
            FROM bookings b
            LEFT JOIN LATERAL jsonb_array_elements(b.items) AS item ON TRUE
            GROUP BY b.id
        )
        UPDATE bookings b
        SET total_amount =
            GREATEST(0, pb.subtotal - (pb.d_amt + pb.subtotal * pb.d_pct / 100))
            + GREATEST(0, pb.subtotal - (pb.d_amt + pb.subtotal * pb.d_pct / 100)) * pb.gst_pct / 100
            + pb.transport
        FROM per_booking pb
        WHERE b.id = pb.id;
    """)

    # ----- Privacy-hardened Realtime -----
    # Tighten RLS: drop the broad anon SELECT on bookings (which exposed customer PII
    # in realtime payloads). Instead, fan out change events through a non-PII signal
    # table that only carries (id, booking_id, branch_id, action, created_at).
    op.execute("DROP POLICY IF EXISTS bookings_anon_read ON bookings;")

    op.create_table(
        "bookings_signal",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("booking_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("branch_id", sa.dialects.postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bookings_signal_branch", "bookings_signal", ["branch_id"])
    op.create_index("ix_bookings_signal_created_at", "bookings_signal", ["created_at"])
    op.execute("ALTER TABLE bookings_signal ENABLE ROW LEVEL SECURITY;")
    op.execute("CREATE POLICY bookings_signal_anon_read ON bookings_signal FOR SELECT TO anon USING (true);")

    # Trigger: every change on bookings emits a signal row (with only IDs/branch/action).
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_emit_bookings_signal()
        RETURNS TRIGGER AS $$
        DECLARE
            v_action text := lower(TG_OP);
            v_booking uuid;
            v_branch uuid;
        BEGIN
            IF TG_OP = 'DELETE' THEN
                v_booking := OLD.id; v_branch := OLD.branch_id;
            ELSE
                v_booking := NEW.id; v_branch := NEW.branch_id;
            END IF;
            INSERT INTO bookings_signal (booking_id, branch_id, action)
            VALUES (v_booking, v_branch, v_action);
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_bookings_signal ON bookings;")
    op.execute("""
        CREATE TRIGGER trg_bookings_signal
        AFTER INSERT OR UPDATE OR DELETE ON bookings
        FOR EACH ROW EXECUTE FUNCTION fn_emit_bookings_signal();
    """)

    # Move the realtime publication from bookings → bookings_signal.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
                BEGIN EXECUTE 'ALTER PUBLICATION supabase_realtime DROP TABLE bookings';
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE bookings_signal';
                EXCEPTION WHEN duplicate_object THEN NULL; END;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_publication WHERE pubname = 'supabase_realtime') THEN
                BEGIN EXECUTE 'ALTER PUBLICATION supabase_realtime DROP TABLE bookings_signal';
                EXCEPTION WHEN OTHERS THEN NULL; END;
                BEGIN EXECUTE 'ALTER PUBLICATION supabase_realtime ADD TABLE bookings';
                EXCEPTION WHEN OTHERS THEN NULL; END;
            END IF;
        END $$;
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_bookings_signal ON bookings;")
    op.execute("DROP FUNCTION IF EXISTS fn_emit_bookings_signal();")
    op.execute("DROP POLICY IF EXISTS bookings_signal_anon_read ON bookings_signal;")
    op.drop_index("ix_bookings_signal_created_at", table_name="bookings_signal")
    op.drop_index("ix_bookings_signal_branch", table_name="bookings_signal")
    op.drop_table("bookings_signal")
    op.execute("CREATE POLICY bookings_anon_read ON bookings FOR SELECT TO anon USING (true);")
    op.drop_column('bookings', 'total_amount')
