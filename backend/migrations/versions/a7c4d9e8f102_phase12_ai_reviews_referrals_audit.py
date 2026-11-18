"""phase12_ai_reviews_referrals_audit

Revision ID: a7c4d9e8f102
Revises: 41395fdbf8b0
Create Date: 2026-11-12 22:32:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c4d9e8f102'
down_revision: Union[str, Sequence[str], None] = '41395fdbf8b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 12 AI runs, per-eye results, clinical reviews, referrals, and audit log tables."""
    op.drop_constraint('ck_screenings_status', 'screenings', type_='check')
    op.create_check_constraint(
        'ck_screenings_status',
        'screenings',
        "status IN ('draft', 'awaiting_images', 'images_incomplete', "
        "'ready_for_quality_assessment', 'quality_failed_recapture_required', "
        "'ai_completed_review_required', 'ai_completed_advisory', "
        "'ai_failed_review_required', 'clinically_reviewed_signed', "
        "'cancelled', 'archived')",
    )

    op.create_table(
        'screening_ai_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('screening_id', sa.String(length=36), nullable=False),
        sa.Column('owner_user_id', sa.String(length=36), nullable=False),
        sa.Column('triggered_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('model_key', sa.String(length=100), nullable=False),
        sa.Column('model_version', sa.String(length=64), nullable=False),
        sa.Column('architecture', sa.String(length=64), nullable=False),
        sa.Column('checkpoint_sha256', sa.String(length=64), nullable=False),
        sa.Column('checkpoint_epoch', sa.Integer(), nullable=False),
        sa.Column('preprocessing_config_json', sa.Text(), nullable=False),
        sa.Column('overall_status', sa.String(length=40), nullable=False),
        sa.Column('overall_review_required', sa.Boolean(), nullable=False),
        sa.Column('overall_escalation_reasons_json', sa.Text(), nullable=False),
        sa.Column('higher_risk_eye', sa.String(length=2), nullable=True),
        sa.Column('highest_predicted_grade', sa.Integer(), nullable=True),
        sa.Column('highest_predicted_label', sa.String(length=64), nullable=True),
        sa.Column('research_disclaimer', sa.Text(), nullable=False),
        sa.Column('calibration_warning', sa.Text(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('execution_ms', sa.Integer(), nullable=False),
        sa.Column('inference_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "overall_status IN ('completed', 'quality_failed', 'failed')",
            name='ck_screening_ai_runs_status',
        ),
        sa.CheckConstraint(
            "higher_risk_eye IS NULL OR higher_risk_eye IN ('OD', 'OS')",
            name='ck_screening_ai_runs_eye',
        ),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['screening_id'], ['screenings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['triggered_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ai_runs_owner_ts', 'screening_ai_runs', ['owner_user_id', 'inference_timestamp'], unique=False)
    op.create_index('ix_ai_runs_screening_ts', 'screening_ai_runs', ['screening_id', 'inference_timestamp'], unique=False)
    op.create_index(op.f('ix_screening_ai_runs_overall_status'), 'screening_ai_runs', ['overall_status'], unique=False)
    op.create_index(op.f('ix_screening_ai_runs_owner_user_id'), 'screening_ai_runs', ['owner_user_id'], unique=False)
    op.create_index(op.f('ix_screening_ai_runs_screening_id'), 'screening_ai_runs', ['screening_id'], unique=False)

    op.create_table(
        'screening_ai_eye_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('ai_run_id', sa.String(length=36), nullable=False),
        sa.Column('screening_id', sa.String(length=36), nullable=False),
        sa.Column('screening_image_id', sa.String(length=36), nullable=False),
        sa.Column('eye', sa.String(length=2), nullable=False),
        sa.Column('gradable', sa.Boolean(), nullable=False),
        sa.Column('quality_status', sa.String(length=40), nullable=False),
        sa.Column('quality_reason', sa.Text(), nullable=True),
        sa.Column('quality_metrics_json', sa.Text(), nullable=False),
        sa.Column('predicted_grade', sa.Integer(), nullable=True),
        sa.Column('predicted_label', sa.String(length=64), nullable=True),
        sa.Column('probabilities_json', sa.Text(), nullable=False),
        sa.Column('confidence_max_prob', sa.Float(), nullable=True),
        sa.Column('top2_margin', sa.Float(), nullable=True),
        sa.Column('normalized_entropy', sa.Float(), nullable=True),
        sa.Column('vtdr_prob_sum', sa.Float(), nullable=True),
        sa.Column('uncertainty_review_required', sa.Boolean(), nullable=False),
        sa.Column('uncertainty_reasons_json', sa.Text(), nullable=False),
        sa.Column('high_risk_flagged', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("eye IN ('OD', 'OS')", name='ck_ai_eye_results_eye'),
        sa.CheckConstraint(
            "quality_status IN ('gradable', 'ungradable_image_quality', 'decode_error')",
            name='ck_ai_eye_results_quality_status',
        ),
        sa.CheckConstraint(
            '(gradable IS TRUE) OR (predicted_grade IS NULL AND predicted_label IS NULL)',
            name='ck_ai_eye_results_no_forced_grade',
        ),
        sa.ForeignKeyConstraint(['ai_run_id'], ['screening_ai_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['screening_id'], ['screenings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['screening_image_id'], ['screening_images.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_screening_ai_eye_results_ai_run_id'), 'screening_ai_eye_results', ['ai_run_id'], unique=False)
    op.create_index(op.f('ix_screening_ai_eye_results_screening_id'), 'screening_ai_eye_results', ['screening_id'], unique=False)
    op.create_index('uq_ai_eye_results_run_eye', 'screening_ai_eye_results', ['ai_run_id', 'eye'], unique=True)

    op.create_table(
        'clinical_reviews',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('screening_id', sa.String(length=36), nullable=False),
        sa.Column('owner_user_id', sa.String(length=36), nullable=False),
        sa.Column('reviewer_user_id', sa.String(length=36), nullable=False),
        sa.Column('linked_ai_run_id', sa.String(length=36), nullable=True),
        sa.Column('reviewer_name_snapshot', sa.String(length=255), nullable=False),
        sa.Column('reviewer_registration_number_snapshot', sa.String(length=100), nullable=False),
        sa.Column('od_confirmed_grade', sa.Integer(), nullable=True),
        sa.Column('od_confirmed_label', sa.String(length=64), nullable=True),
        sa.Column('os_confirmed_grade', sa.Integer(), nullable=True),
        sa.Column('os_confirmed_label', sa.String(length=64), nullable=True),
        sa.Column('worst_eye_confirmed_grade', sa.Integer(), nullable=True),
        sa.Column('worst_eye_confirmed_label', sa.String(length=64), nullable=True),
        sa.Column('ai_agreement_status', sa.String(length=40), nullable=False),
        sa.Column('override_rationale', sa.Text(), nullable=True),
        sa.Column('clinical_findings', sa.Text(), nullable=False),
        sa.Column('follow_up_plan', sa.String(length=100), nullable=False),
        sa.Column('recapture_required', sa.Boolean(), nullable=False),
        sa.Column('is_signed', sa.Boolean(), nullable=False),
        sa.Column('signed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "ai_agreement_status IN ('agreed_with_ai', 'overrode_ai', 'independent_no_ai', 'recapture_ordered')",
            name='ck_clinical_reviews_agreement',
        ),
        sa.CheckConstraint(
            'od_confirmed_grade IS NULL OR (od_confirmed_grade >= 0 AND od_confirmed_grade <= 4)',
            name='ck_clinical_reviews_od_grade',
        ),
        sa.CheckConstraint(
            'os_confirmed_grade IS NULL OR (os_confirmed_grade >= 0 AND os_confirmed_grade <= 4)',
            name='ck_clinical_reviews_os_grade',
        ),
        sa.ForeignKeyConstraint(['linked_ai_run_id'], ['screening_ai_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewer_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['screening_id'], ['screenings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_clinical_reviews_owner_signed', 'clinical_reviews', ['owner_user_id', 'signed_at'], unique=False)
    op.create_index(op.f('ix_clinical_reviews_owner_user_id'), 'clinical_reviews', ['owner_user_id'], unique=False)
    op.create_index(op.f('ix_clinical_reviews_screening_id'), 'clinical_reviews', ['screening_id'], unique=True)

    op.create_table(
        'referrals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('referral_reference', sa.String(length=64), nullable=False),
        sa.Column('screening_id', sa.String(length=36), nullable=False),
        sa.Column('clinical_review_id', sa.String(length=36), nullable=False),
        sa.Column('patient_id', sa.String(length=36), nullable=False),
        sa.Column('owner_user_id', sa.String(length=36), nullable=False),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=False),
        sa.Column('urgency', sa.String(length=40), nullable=False),
        sa.Column('target_specialty', sa.String(length=120), nullable=False),
        sa.Column('target_facility', sa.String(length=255), nullable=False),
        sa.Column('reason_summary', sa.Text(), nullable=False),
        sa.Column('clinical_summary', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('appointment_notes', sa.Text(), nullable=True),
        sa.Column('dispatched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('DISPATCHED', 'ACCEPTED', 'APPOINTMENT_SCHEDULED', 'COMPLETED', 'CANCELLED')",
            name='ck_referrals_status',
        ),
        sa.CheckConstraint(
            "urgency IN ('IMMEDIATE_48H', 'WITHIN_2_WEEKS', 'STANDARD_SURVEILLANCE')",
            name='ck_referrals_urgency',
        ),
        sa.ForeignKeyConstraint(['clinical_review_id'], ['clinical_reviews.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['screening_id'], ['screenings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_referrals_owner_dispatched', 'referrals', ['owner_user_id', 'dispatched_at'], unique=False)
    op.create_index(op.f('ix_referrals_clinical_review_id'), 'referrals', ['clinical_review_id'], unique=False)
    op.create_index(op.f('ix_referrals_owner_user_id'), 'referrals', ['owner_user_id'], unique=False)
    op.create_index(op.f('ix_referrals_patient_id'), 'referrals', ['patient_id'], unique=False)
    op.create_index(op.f('ix_referrals_referral_reference'), 'referrals', ['referral_reference'], unique=True)
    op.create_index(op.f('ix_referrals_screening_id'), 'referrals', ['screening_id'], unique=False)
    op.create_index(op.f('ix_referrals_status'), 'referrals', ['status'], unique=False)
    op.create_index(op.f('ix_referrals_urgency'), 'referrals', ['urgency'], unique=False)

    op.create_table(
        'clinical_audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('owner_user_id', sa.String(length=36), nullable=False),
        sa.Column('actor_user_id', sa.String(length=36), nullable=False),
        sa.Column('screening_id', sa.String(length=36), nullable=True),
        sa.Column('patient_id', sa.String(length=36), nullable=True),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['patient_id'], ['patients.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['screening_id'], ['screenings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_owner_screening_ts', 'clinical_audit_logs', ['owner_user_id', 'screening_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_clinical_audit_logs_created_at'), 'clinical_audit_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_clinical_audit_logs_event_type'), 'clinical_audit_logs', ['event_type'], unique=False)
    op.create_index(op.f('ix_clinical_audit_logs_owner_user_id'), 'clinical_audit_logs', ['owner_user_id'], unique=False)
    op.create_index(op.f('ix_clinical_audit_logs_patient_id'), 'clinical_audit_logs', ['patient_id'], unique=False)
    op.create_index(op.f('ix_clinical_audit_logs_screening_id'), 'clinical_audit_logs', ['screening_id'], unique=False)


def downgrade() -> None:
    """Drop Phase 12 tables and restore previous screening status constraint."""
    op.drop_index(op.f('ix_clinical_audit_logs_screening_id'), table_name='clinical_audit_logs')
    op.drop_index(op.f('ix_clinical_audit_logs_patient_id'), table_name='clinical_audit_logs')
    op.drop_index(op.f('ix_clinical_audit_logs_owner_user_id'), table_name='clinical_audit_logs')
    op.drop_index(op.f('ix_clinical_audit_logs_event_type'), table_name='clinical_audit_logs')
    op.drop_index(op.f('ix_clinical_audit_logs_created_at'), table_name='clinical_audit_logs')
    op.drop_index('ix_audit_owner_screening_ts', table_name='clinical_audit_logs')
    op.drop_table('clinical_audit_logs')

    op.drop_index(op.f('ix_referrals_urgency'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_status'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_screening_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_referral_reference'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_patient_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_owner_user_id'), table_name='referrals')
    op.drop_index(op.f('ix_referrals_clinical_review_id'), table_name='referrals')
    op.drop_index('ix_referrals_owner_dispatched', table_name='referrals')
    op.drop_table('referrals')

    op.drop_index(op.f('ix_clinical_reviews_screening_id'), table_name='clinical_reviews')
    op.drop_index(op.f('ix_clinical_reviews_owner_user_id'), table_name='clinical_reviews')
    op.drop_index('ix_clinical_reviews_owner_signed', table_name='clinical_reviews')
    op.drop_table('clinical_reviews')

    op.drop_index('uq_ai_eye_results_run_eye', table_name='screening_ai_eye_results')
    op.drop_index(op.f('ix_screening_ai_eye_results_screening_id'), table_name='screening_ai_eye_results')
    op.drop_index(op.f('ix_screening_ai_eye_results_ai_run_id'), table_name='screening_ai_eye_results')
    op.drop_table('screening_ai_eye_results')

    op.drop_index(op.f('ix_screening_ai_runs_screening_id'), table_name='screening_ai_runs')
    op.drop_index(op.f('ix_screening_ai_runs_owner_user_id'), table_name='screening_ai_runs')
    op.drop_index(op.f('ix_screening_ai_runs_overall_status'), table_name='screening_ai_runs')
    op.drop_index('ix_ai_runs_screening_ts', table_name='screening_ai_runs')
    op.drop_index('ix_ai_runs_owner_ts', table_name='screening_ai_runs')
    op.drop_table('screening_ai_runs')

    op.drop_constraint('ck_screenings_status', 'screenings', type_='check')
    op.create_check_constraint(
        'ck_screenings_status',
        'screenings',
        "status IN ('draft', 'awaiting_images', 'images_incomplete', "
        "'ready_for_quality_assessment', 'cancelled', 'archived')",
    )

