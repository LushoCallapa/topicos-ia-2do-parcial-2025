import dspy
import sqlite3
from dotenv import load_dotenv

from tools import execute_sql, get_schema, save_data_to_csv


# --- DSPy Agent Definition ---
class SQLAgentSignature(dspy.Signature):
    """
    You are an intelligent SQL Agent that converts natural language questions into SQL queries.
    
    Tasks:
    - Understand user intent and translate it into valid SQL queries.
    - Use the database schema to generate accurate SQL.
    - Execute the query safely using the available tools.

    You may perform the following:
    - SELECT queries for data retrieval.
    - INSERT, UPDATE, DELETE for modifying data when explicitly requested by the user (e.g., "add", "create", "update", "remove").

    Available Tools:
    - execute_sql(query): Executes any SQL command (SELECT or modification).
    - get_schema(): View database structure.
    - save_data_to_csv(): Export results when user requests.

    Safety:
    - Always verify the target table and column names before modifying data.
    - Do not drop or alter tables.
    - Confirm success after modifications.
    """

    question = dspy.InputField(desc="The user's natural language question.")
    initial_schema = dspy.InputField(desc="The initial database schema to guide you.")
    answer = dspy.OutputField(
        desc="The final, natural language answer to the user's question."
    )


class SQLAgent(dspy.Module):
    """The SQL Agent Module"""
    def __init__(self, tools: list[dspy.Tool]):
        super().__init__()
        # Initialize the ReAct agent.
        self.agent = dspy.ReAct(
            SQLAgentSignature,
            tools=tools,
            max_iters=7,  # Set a max number of steps
        )

    def forward(self, question: str, initial_schema: str) -> dspy.Prediction:
        """The forward pass of the module."""
        result = self.agent(question=question, initial_schema=initial_schema)
        return result


def configure_llm():
    """Configures the DSPy language model."""
    load_dotenv()
    llm = dspy.LM(model="openai/gpt-4o-mini", max_tokens=4000)
    dspy.settings.configure(lm=llm)

    print("[Agent] DSPy configured with gpt-4o-mini model.")
    return llm


def create_agent(conn: sqlite3.Connection, query_history: list[str] | None = None) -> dspy.Module | None:
    if not configure_llm():
        return

    execute_sql_tool = dspy.Tool(
        name="execute_sql",
        desc="Executes a SQL query on the database. Input: query (str) - A valid SQL query string. Output: (str) - Query results as a string representation of rows, or an error message if the query fails. Use this tool to retrieve data from the database.",
        # Use lambda to pass the 'conn' object
        func=lambda query: execute_sql(conn, query, query_history),
    )

    get_schema_tool = dspy.Tool(
        name="get_schema",
        desc="Gets the database schema information. Input: table_name (str or None) - If None, returns a list of all table names. If a table name is provided, returns the columns and their types for that specific table. Output: (str) - String representation of table names or column information. Use this to explore the database structure.",
        # Use lambda to pass the 'conn' object
        func=lambda table_name: get_schema(conn, table_name),
    )

    save_csv_tool = dspy.Tool(
        name="save_data_to_csv",
        desc="Creates an individual CSV file with query results when the user explicitly asks to save/export data. Input: data (list[tuple]) - Data rows to save, filename (str, optional) - Name for the CSV file, query_description (str, optional) - Description to include. Output: (str) - Success message with file path. NOTE: All SELECT queries are already auto-saved to 'query_results.csv', so only use this tool when the user specifically requests to save/export to a named file.",
        func=save_data_to_csv
    )

    all_tools = [execute_sql_tool, get_schema_tool, save_csv_tool]

    # 2. Instantiate and run the agent
    agent = SQLAgent(tools=all_tools)

    return agent