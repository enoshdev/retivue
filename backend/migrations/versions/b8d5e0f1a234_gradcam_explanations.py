"""gradcam_explanations

Revision ID: b8d5e0f1a234
Revises: a7c4d9e8f102
Create Date: 2026-11-13 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d5e0f1a234'
down_revision: Union[str, Sequence[str], None] = 'a7c4d9e8f102'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'screening_ai_explanations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('screening_id', sa.String(length=36), nullable=False),
        sa.Column('screening_image_id', sa.String(length=36), nullable=False),
        sa.Column('ai_run_id', sa.String(length=36), nullable=False),
        sa.Column('owner_user_id', sa.String(length=36), nullable=False),
        sa.Column('eye', sa.String(length=2), nullable=False),
        sa.Column('target_class', sa.Integer(), nullable=False),
        sa.Column('target_class_label', sa.String(length=64), nullable=False),
        sa.Column('is_default_target', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('explanation_text', sa.Text(), nullable=False),
        sa.Column('model_layer', sa.String(length=64), nullable=False, server_default='features.8'),
        sa.Column('image_sha256', sa.String(length=64), nullable=False),
        sa.Column('checkpoint_sha256', sa.String(length=64), nullable=False),
        sa.Column('heatmap_storage_key', sa.String(length=512), nullable=True),
        sa.Column('overlay_storage_key', sa.String(length=512), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("eye IN ('OD', 'OS')", name='ck_ai_explanations_eye'),
        sa.CheckConstraint("target_class BETWEEN 0 AND 4", name='ck_ai_explanations_target_class'),
        sa.CheckConstraint("status IN ('completed', 'unavailable_ungradable', 'failed')", name='ck_ai_explanations_status'),
        sa.ForeignKeyConstraint(['ai_run_id'], ['screening_ai_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['screening_id'], ['screenings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['screening_image_id'], ['screening_images.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_explanations_screening_id', 'screening_ai_explanations', ['screening_id'])
    op.create_index('ix_ai_explanations_screening_image_id', 'screening_ai_explanations', ['screening_image_id'])
    op.create_index('ix_ai_explanations_ai_run_id', 'screening_ai_explanations', ['ai_run_id'])
    op.create_index('ix_ai_explanations_owner_user_id', 'screening_ai_explanations', ['owner_user_id'])
    op.create_index('ix_ai_explanations_lookup', 'screening_ai_explanations', ['screening_id', 'eye', 'target_class'])
    op.create_index('uq_ai_explanations_cache', 'screening_ai_explanations', ['screening_image_id', 'checkpoint_sha256', 'target_class'], unique=True)


def downgrade() -> None:
    op.drop_index('uq_ai_explanations_cache', table_name='screening_ai_explanations')
    op.drop_index('ix_ai_explanations_lookup', table_name='screening_ai_explanations')
    op.drop_index('ix_ai_explanations_owner_user_id', table_name='screening_ai_explanations')
    op.drop_index('ix_ai_explanations_ai_run_id', table_name='screening_ai_explanations')
    op.drop_index('ix_ai_explanations_screening_image_id', table_name='screening_ai_explanations')
    op.drop_index('ix_ai_explanations_screening_id', table_name='screening_ai_explanations')
    op.drop_table('screening_ai_explanations')

