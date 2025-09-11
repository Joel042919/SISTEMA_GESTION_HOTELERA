from psycopg_pool import ConnectionPool
from .config import settings


POOL = ConnectionPool(
    #conninfo= f"host={settings.db_host} port={settings.db_port} dbname={settings.db_name} user={settings.db_user} password={settings.db_password}",
    conninfo=settings.DB_DSN,
    min_size=1,
    max_size=10,
    kwargs={"autocommit": False}
)


class PgSession:
    def __enter__(self):
        self.conn = POOL.getconn()
        self.cur = self.conn.cursor()
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:    
            self.cur.close()
            POOL.putconn(self.conn)

    def call(self, fn: str, params: tuple = ()): # devuelve first row
        placeholders = ', '.join(['%s']*len(params))
        self.cur.execute(f"SELECT * FROM {fn}({placeholders});", params)
        try:
            return self.cur.fetchone()
        except Exception:
            return None

    def call_void(self, fn: str, params: tuple = ()): # para VOID
        placeholders = ', '.join(['%s']*len(params))
        self.cur.execute(f"SELECT {fn}({placeholders});", params)