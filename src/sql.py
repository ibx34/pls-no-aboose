import logging

import asyncpg

log = logging.getLogger(__name__)


async def init_db(db_config, size):

    try:
        pool = await asyncpg.create_pool(**db_config, max_size=size)

        with open("src/schema.sql") as f:
            await pool.execute(f.read())

        return pool
    except Exception as error:
        log.exception(f"Creating pool failed.", exc_info=error)
