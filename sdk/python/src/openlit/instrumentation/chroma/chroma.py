"""
Module for monitoring ChromaDB API calls.
"""

import time
from opentelemetry.trace import SpanKind
from opentelemetry import context as context_api
from openlit.__helpers import handle_exception
from openlit.instrumentation.chroma.utils import (
    process_vectordb_response,
    DB_OPERATION_MAP,
    set_server_address_and_port,
)


def general_wrap(
    gen_ai_endpoint,
    version,
    environment,
    application_name,
    tracer,
    pricing_info,
    capture_message_content,
    metrics,
    disable_metrics,
):
    """
    Generates a telemetry wrapper for ChromaDB function calls.
    """

    def wrapper(wrapped, instance, args, kwargs):
        """
        Wraps the ChromaDB function call.
        """

        if context_api.get_value(context_api._SUPPRESS_INSTRUMENTATION_KEY):
            return wrapped(*args, **kwargs)

        # Get server address and port using the standard helper
        server_address, server_port = set_server_address_and_port(instance)

        db_operation = DB_OPERATION_MAP.get(gen_ai_endpoint, "unknown")
        if db_operation == "create_collection":
            namespace = kwargs.get("name") or (args[0] if args else "unknown")
        else:
            namespace = getattr(instance, "name", "unknown")
        span_name = f"{db_operation} {namespace}"

        with tracer.start_as_current_span(span_name, kind=SpanKind.CLIENT) as span:
            start_time = time.time()
            response = wrapped(*args, **kwargs)

            try:
                # Process response and generate telemetry
                response = process_vectordb_response(
                    response,
                    db_operation,
                    server_address,
                    server_port,
                    environment,
                    application_name,
                    metrics,
                    start_time,
                    span,
                    capture_message_content,
                    disable_metrics,
                    version,
                    instance,
                    args,
                    endpoint=gen_ai_endpoint,
                    **kwargs,
                )

            except Exception as e:
                handle_exception(span, e)

            return response

    return wrapper
