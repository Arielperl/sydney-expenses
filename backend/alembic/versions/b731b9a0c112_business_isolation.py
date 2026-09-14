"""Add businesses and preserve existing records under the legacy business."""
from alembic import op
import sqlalchemy as sa
revision = 'b731b9a0c112'
down_revision = 'f2ee09240842'
branch_labels = depends_on = None
LEGACY = '00000000-0000-4000-8000-000000000001'

def upgrade():
    op.create_table('businesses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('country_code', sa.String(2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('timezone', sa.String(64), nullable=False),
        sa.Column('vat_rate', sa.Numeric(6,4), nullable=False),
        sa.Column('business_number', sa.String(30)),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.execute(sa.text("INSERT INTO businesses (id,name,country_code,currency,timezone,vat_rate,created_at) VALUES (:id,:name,'IL','ILS','Asia/Jerusalem',0.18,CURRENT_TIMESTAMP)").bindparams(id=LEGACY,name='העסק של אריאל'))
    op.create_table('business_members',
        sa.Column('business_id', sa.String(36), sa.ForeignKey('businesses.id'), primary_key=True),
        sa.Column('user_id', sa.String(128), primary_key=True, unique=True),
        sa.Column('role', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("role in ('owner','manager','viewer')",name='ck_member_role'))
    for table in ('import_batches','sales','sale_events'):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column('business_id',sa.String(36),nullable=False,server_default=LEGACY))
            batch.create_foreign_key('fk_'+table+'_business','businesses',['business_id'],['id'])
            batch.create_index('ix_'+table+'_business_id',['business_id'])
        with op.batch_alter_table(table) as batch:
            batch.alter_column('business_id',server_default=None)
    with op.batch_alter_table('sales') as batch:
        batch.drop_constraint('uq_sales_source_provider_external_id',type_='unique')
        batch.create_unique_constraint('uq_sales_source_provider_external_id',['business_id','source_provider','external_id'])
    if op.get_bind().dialect.name == 'postgresql':
        for table in ('businesses', 'business_members', 'sales', 'sale_events', 'import_batches'):
            op.execute(sa.text('ALTER TABLE "'+table+'" ENABLE ROW LEVEL SECURITY'))

def downgrade():
    raise RuntimeError('Business isolation cannot be removed safely with multiple businesses. Restore a verified backup instead.')
