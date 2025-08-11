"""merge heads

Revision ID: a20d5e23f0eb
Revises: dbaab40ed659, ea3777bbdea0
Create Date: 2025-08-09 10:27:41.178267

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a20d5e23f0eb'
down_revision: Union[str, Sequence[str], None] = ('dbaab40ed659', 'ea3777bbdea0')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
