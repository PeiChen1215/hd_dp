from alembic.config import Config
from alembic import command

cfg = Config("alembic.ini")

# create autogenerate revision and apply it
command.revision(cfg, autogenerate=True, message="init")
command.upgrade(cfg, "head")

print("Alembic revision + upgrade completed.")
