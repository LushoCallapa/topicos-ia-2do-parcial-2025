import ast
import sqlite3
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import FastAPI, Depends, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import dspy

from database import setup_database
from tools import get_schema, execute_sql
from agent import create_agent

app = FastAPI(title="AI DB Assistant")

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

query_history = []

# --- MODELOS ---
class AgentResponse(BaseModel):
    original_query: str
    sql_queries: list[str]
    agent_answer: str

class AgentAsyncStartResponse(BaseModel):
    query_id: uuid.UUID
    status: str = "pending"

class AgentAsyncFinishResponse(AgentResponse):
    query_id: uuid.UUID
    status: str = "finished"


# --- DEPENDENCIAS ---
def get_db_connection() -> sqlite3.Connection:
    return setup_database()

def get_db_schema(conn: Annotated[sqlite3.Connection, Depends(get_db_connection)]) -> str:
    return get_schema(conn)

def get_agent(conn: Annotated[sqlite3.Connection, Depends(get_db_connection)]) -> dspy.Module:
    return create_agent(conn, query_history)


# --- FUNCIONES PRINCIPALES ---
def query_agent(agent, user_query, db_schema):
    """Ejecuta una consulta natural sobre la BD usando el agente."""
    outputs = agent(question=user_query, initial_schema=db_schema)
    results = AgentResponse(
        original_query=user_query,
        sql_queries=query_history.copy(),
        agent_answer=outputs.answer,
    )
    query_history.clear()
    return results


def run_async_query(agent, user_query, db_schema, query_id):
    """Ejecuta una consulta en segundo plano (con nueva conexión SQLite)."""
    conn = setup_database()
    try:
        result = query_agent(agent, user_query, db_schema)
        results_json = result.model_dump_json()
        cur = conn.cursor()
        cur.execute(
            "UPDATE queries SET status = ?, result = ? WHERE id = ?",
            ("finished", results_json, str(query_id)),
        )
        conn.commit()
        print(f"[OK] Consulta {query_id} finalizada correctamente.")
    except Exception as e:
        cur = conn.cursor()
        cur.execute(
            "UPDATE queries SET status = ?, result = ? WHERE id = ?",
            ("error", str(e), str(query_id)),
        )
        conn.commit()
        print(f"[ERROR] Fallo en consulta {query_id}: {e}")
    finally:
        conn.close()


# --- ENDPOINTS ---
@app.post("/database/natural_queries")
def query_database(
    db_schema: Annotated[str, Depends(get_db_schema)],
    agent: Annotated[dspy.Module, Depends(get_agent)],
    user_query: str = Body(..., embed=True),
) -> AgentResponse:
    """Consulta sincrónica directa."""
    return query_agent(agent, user_query, db_schema)


@app.post("/database/async_queries")
def async_query_database(
    db_schema: Annotated[str, Depends(get_db_schema)],
    agent: Annotated[dspy.Module, Depends(get_agent)],
    background_tasks: BackgroundTasks,
    db_conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
    user_query: str = Body(..., embed=True),
) -> AgentAsyncStartResponse:
    """Inicia consulta asíncrona."""
    query_id = uuid.uuid4()
    execute_sql(
        db_conn,
        f"INSERT INTO queries (id, status, result) VALUES ('{query_id}', 'pending', '')",
    )
    db_conn.commit()
    background_tasks.add_task(run_async_query, agent, user_query, db_schema, query_id)
    return AgentAsyncStartResponse(query_id=query_id)


@app.get("/database/async_queries")
def get_async_query_result(
    db_conn: Annotated[sqlite3.Connection, Depends(get_db_connection)],
    query_id: uuid.UUID,
):
    """Obtiene el resultado de una consulta asíncrona."""
    result = execute_sql(db_conn, f"SELECT * FROM queries WHERE id = '{query_id}'")
    rows = ast.literal_eval(result)
    if not rows:
        return {"error": "Consulta no encontrada"}
    row = rows[0]

    status = row[1]
    if status == "pending":
        return AgentAsyncStartResponse(query_id=query_id, status="pending")
    elif status == "error":
        return {"query_id": str(query_id), "status": "error", "error": row[2]}

    # Si ya terminó, devolvemos el resultado
    response = AgentResponse.model_validate_json(row[2])
    return AgentAsyncFinishResponse(
        original_query=response.original_query,
        sql_queries=response.sql_queries,
        agent_answer=response.agent_answer,
        query_id=query_id,
        status="finished",
    )

app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
