import os
import sqlite3
import csv
from datetime import datetime
import ast

def _auto_save_to_global_csv(query: str, result: str) -> None:
    try:
        if query.strip().upper().startswith('SELECT'):
            try:
                data = ast.literal_eval(result)
                if not data or not isinstance(data, list):
                    return
            except:
                return
            file = "query_results.csv"
            abs_path = os.path.abspath(file)
            exists = os.path.exists(abs_path)
            with open(abs_path, 'a', newline='', encoding='utf-8') as csvfile:
                w = csv.writer(csvfile)
                if exists:
                    w.writerow([])
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                w.writerow([f"=== AUTO-SAVED Query at: {ts} ==="])
                w.writerow([f"SQL: {query[:100]}..."])
                w.writerows(data)
            print(f"   [Auto-Save] Query results saved to {file}")
        elif query.strip().lower().startswith(("insert", "update", "delete")):
            file = "modifications_log.csv"
            abs_path = os.path.abspath(file)
            with open(abs_path, 'a', newline='', encoding='utf-8') as csvfile:
                w = csv.writer(csvfile)
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                w.writerow([ts, query])
            print(f"   [Auto-Save] Modification query logged to {file}")
    except:
        pass

def execute_sql(conn: sqlite3.Connection, query: str, query_history: list[str] | None = None) -> str:
    print(f"   [BEGIN Tool Action] Executing SQL: {query} [END Tool Action]")
    if query_history is not None:
        query_history.append(query)
    try:
        cur = conn.cursor()
        cur.execute(query)
        if cur.description:
            rows = cur.fetchall()
            result = str(rows)
            _auto_save_to_global_csv(query, result)
            return result
        else:
            conn.commit()
            _auto_save_to_global_csv(query, "")
            if query.strip().lower().startswith(("insert", "update", "delete")):
                try:
                    cur.execute(
                        "INSERT INTO queries (id, status, result) VALUES (?, ?, ?)",
                        (str(hash(query)), "executed", query)
                    )
                    conn.commit()
                except Exception:
                    pass
            return "Query executed successfully (no data returned)."
    except sqlite3.Error as e:
        return f"Error: {e}"

def get_schema(conn: sqlite3.Connection, table_name: str | None = None) -> str:
    print(f"   [Tool Action] Getting schema for: {table_name or 'all tables'}")
    cur = conn.cursor()
    if table_name:
        cur.execute(f"PRAGMA table_info({table_name});")
        cols = cur.fetchall()
        return str([(c[1], c[2]) for c in cols])
    else:
        cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cur.fetchall()
        return str([t[0] for t in tables])

def save_data_to_csv(data: list[tuple], filename: str = "", query_description: str = "") -> str:
    print(f"   [Tool Action] Creating individual CSV file: {filename or 'auto-named'}...")
    try:
        if not data:
            return "Error: No data provided."
        if not isinstance(data, list):
            return f"Error: Data must be a list, received {type(data).__name__}."
        if not filename:
            filename = f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        if not filename.endswith('.csv'):
            filename += '.csv'
        abs_path = os.path.abspath(filename)
        directory = os.path.dirname(abs_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)
        with open(abs_path, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            if query_description:
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                w.writerow([f"Generated at: {ts}"])
                w.writerow([f"Description: {query_description}"])
                w.writerow([])
            w.writerows(data)
        return f"Success: Data saved to {abs_path}"
    except Exception as e:
        return f"Error: {e}"
