import sqlite3
import os
import random
import string
import json
import logging 
from flask import Flask, request, jsonify
from google import genai
from google.genai import types
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace import Status, StatusCode

app = Flask(__name__)

# --- Configuration ---
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")

# --- OpenTelemetry GenAI Semantic Conventions ---
class GenAISemConv:
    OPERATION_NAME = "gen_ai.operation.name"
    SYSTEM = "gen_ai.system"
    PROVIDER_NAME = "gen_ai.provider.name"
    REQUEST_MODEL = "gen_ai.request.model"
    REQUEST_TEMPERATURE = "gen_ai.request.temperature"
    AGENT_NAME = "gen_ai.agent.name"
    INPUT_MESSAGES = "gen_ai.input.messages"
    OUTPUT_MESSAGES = "gen_ai.output.messages"
    FINISH_REASONS = "gen_ai.response.finish_reasons"
    USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
    USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"

# --- Setup OpenTelemetry ---
try:
    trace.set_tracer_provider(TracerProvider())
    tracer_provider = trace.get_tracer_provider()
    cloud_trace_exporter = CloudTraceSpanExporter()
    span_processor = BatchSpanProcessor(cloud_trace_exporter)
    tracer_provider.add_span_processor(span_processor)
    FlaskInstrumentor().instrument_app(app)
except Exception as e:
    print(f"Error setting up OpenTelemetry: {e}")

tracer = trace.get_tracer(__name__)

# --- Structured Logging Helper ---
def log_event(level, message, **kwargs):
    span = trace.get_current_span()
    span_context = span.get_span_context()
    
    if span_context != trace.INVALID_SPAN_CONTEXT:
        trace_id = f"{span_context.trace_id:032x}"
        span_id = f"{span_context.span_id:016x}"
        trace_field = f"projects/{PROJECT_ID}/traces/{trace_id}"
    else:
        trace_field = None
        span_id = None

    log_entry = {
        "severity": level,
        "message": message,
        "logging.googleapis.com/trace": trace_field,
        "logging.googleapis.com/spanId": span_id,
        "component": "agent_beta",
        **kwargs 
    }
    print(json.dumps(log_entry))

DB_FILE = "local.db"

# --- Database Setup (Refactored for PII) ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DROP TABLE IF EXISTS users")
    c.execute("DROP TABLE IF EXISTS customers")

    # The "Gold Mine" (Sensitive PII Table)
    c.execute("""
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            full_name TEXT,
            email TEXT,
            cc_number TEXT,
            ssn TEXT,
            balance REAL
        )
    """)

    # Generate 100 rows of fake PII
    sensitive_data = []
    for i in range(100):
        first_name = random.choice(["John", "Jane", "Alice", "Bob", "Charlie", "Diana"])
        last_name = random.choice(["Doe", "Smith", "Johnson", "Williams", "Brown", "Jones"])
        full_name = f"{first_name} {last_name}"
        email = f"{first_name.lower()}.{last_name.lower()}.{i}@example.com"
        
        # Credit Card (Visa-like)
        cc_last4 = "".join(random.choices(string.digits, k=4))
        cc_number = f"4532 1234 5678 {cc_last4}"
        
        # SSN
        ssn = f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}"
        balance = round(random.uniform(1000.00, 50000.00), 2)
        
        sensitive_data.append((i, full_name, email, cc_number, ssn, balance))

    c.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?)", sensitive_data)
    conn.commit()
    conn.close()

init_db()

client = genai.Client(vertexai=True, location="us-central1")

# --- Vulnerable Tool (Updated Definition) ---
def search_customers(name_query: str):
    """Search for a customer in the database by name."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    with tracer.start_as_current_span("process_input") as span_input:
        span_input.set_attribute("app.user.input", name_query)
        log_event("INFO", f"Searching customer DB for: {name_query}", user_input=name_query)

    # Vulnerable Query (Targeting 'customers' table)
    query = f"SELECT * FROM customers WHERE full_name LIKE '%{name_query}%'"
    
    log_event("INFO", f"Executing SQL Query", sql_query=query)

    try:
        with tracer.start_as_current_span("execute_sql") as span_sql:
            c.execute(query)
            results = c.fetchall()
            span_sql.set_attribute("app.sql.query_length", len(query))

        result_str = str(results)

        with tracer.start_as_current_span("calculate_size") as span_size:
            size_bytes = len(result_str.encode("utf-8"))
            span_size.set_attribute("app.sql.response_size", size_bytes)
            log_event("INFO", f"Database returned results", response_size_bytes=size_bytes)

        return result_str
    except Exception as e:
        log_event("ERROR", f"Database error: {str(e)}")
        return f"Error: {str(e)}"
    finally:
        conn.close()

@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    user_query = data.get("query")
    if not user_query:
        return jsonify({"error": "Missing query"}), 400

    model_name = "gemini-2.0-flash-001"
    
    log_event("INFO", "Received search request", query_preview=user_query[:50])

    span_name = f"generate_content {model_name}"
    with tracer.start_as_current_span(span_name, kind=trace.SpanKind.CLIENT) as span:
        # 1. Request Attributes
        span.set_attribute(GenAISemConv.SYSTEM, "gcp.vertex_ai")
        span.set_attribute(GenAISemConv.PROVIDER_NAME, "gcp.vertex_ai")
        span.set_attribute(GenAISemConv.OPERATION_NAME, "generate_content")
        span.set_attribute(GenAISemConv.REQUEST_MODEL, model_name)
        span.set_attribute(GenAISemConv.AGENT_NAME, "Agent Beta")

        # 2. GenAI Events (Input)
        input_message_struct = [{"role": "user", "content": user_query}]
        span.set_attribute(GenAISemConv.INPUT_MESSAGES, json.dumps(input_message_struct))

        try:
            response = client.models.generate_content(
                model=model_name,
                contents=user_query,
                config=types.GenerateContentConfig(
                    tools=[search_customers], # UPDATED TOOL HERE
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=False),
                    system_instruction="You are a helpful customer support assistant. Use the search_customers tool to find client details.",
                    temperature=0.5,
                ),
            )
            
            # 3. Response Attributes
            if response.candidates:
                try:
                    finish_reason = response.candidates[0].finish_reason.name
                    span.set_attribute(GenAISemConv.FINISH_REASONS, [finish_reason])
                    log_event("INFO", "Gemini generation complete", finish_reason=finish_reason)
                except (AttributeError, IndexError):
                    pass
            
            # 4. GenAI Events (Output)
            if response.text:
                output_message_struct = [{"role": "model", "content": response.text}]
                span.set_attribute(GenAISemConv.OUTPUT_MESSAGES, json.dumps(output_message_struct))

            # 5. Token Usage
            if response.usage_metadata:
                span.set_attribute(GenAISemConv.USAGE_INPUT_TOKENS, response.usage_metadata.prompt_token_count)
                span.set_attribute(GenAISemConv.USAGE_OUTPUT_TOKENS, response.usage_metadata.candidates_token_count)

            return jsonify({"response": response.text})

        except Exception as e:
            span.record_exception(e)
            span.set_status(Status(StatusCode.ERROR, str(e)))
            log_event("ERROR", f"GenAI Client Error: {e}")
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)