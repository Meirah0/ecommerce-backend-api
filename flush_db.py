from tinydb import TinyDB

def flush_database(db_path='ecommerce.json'):
    """Flush (clear) all tables in the TinyDB database."""
    db = TinyDB(db_path)
    
    # List all tables and clear them
    for table_name in db.tables():
        table = db.table(table_name)
        table.truncate()
        print(f"Flushed table: {table_name}")
    
    print("Database flush complete.")

if __name__ == "__main__":
    flush_database()