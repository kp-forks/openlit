"""
PremAI OpenTelemetry instrumentation utility functions
"""

import time

from opentelemetry.trace import Status, StatusCode

from openlit.__helpers import (
    response_as_dict,
    calculate_ttft,
    calculate_tbt,
    get_chat_model_cost,
    get_embed_model_cost,
    general_tokens,
    common_span_attributes,
    record_completion_metrics,
    record_embedding_metrics,
)
from openlit.semcov import SemanticConvention


def format_content(messages):
    """
    Process a list of messages to extract content.
    """

    formatted_messages = []
    for message in messages:
        role = message["role"]
        content = message["content"]

        if isinstance(content, list):
            content_str = ", ".join(
                f"{item['type']}: {item['text'] if 'text' in item else item['image_url']}"
                if "type" in item
                else f"text: {item['text']}"
                for item in content
            )
            formatted_messages.append(f"{role}: {content_str}")
        else:
            formatted_messages.append(f"{role}: {content}")

    return "\n".join(formatted_messages)


def process_chunk(scope, chunk):
    """
    Process a chunk of response data and update state.
    """

    end_time = time.time()
    # Record the timestamp for the current chunk
    scope._timestamps.append(end_time)

    if len(scope._timestamps) == 1:
        # Calculate time to first chunk
        scope._ttft = calculate_ttft(scope._timestamps, scope._start_time)

    chunked = response_as_dict(chunk)
    # Collect message IDs and aggregated response from events
    if chunked.choices:
        first_choice = chunked.get("choices")[0]

        if first_choice.get("delta").get("content"):
            scope._llmresponse += first_choice.get("delta").get("content")

    if chunked.get("choices")[0].get("finish_reason"):
        scope._finish_reason = chunked.get("choices")[0].get("finish_reason")
        scope._response_id = chunked.get("id")
        scope._response_model = chunked.get("model")
        scope._end_time = time.time()


def common_chat_logic(
    scope,
    pricing_info,
    environment,
    application_name,
    metrics,
    capture_message_content,
    disable_metrics,
    version,
    is_stream,
):
    """
    Process chat request and generate Telemetry
    """

    if len(scope._timestamps) > 1:
        scope._tbt = calculate_tbt(scope._timestamps)

    prompt = format_content(scope._kwargs.get("messages", ""))
    request_model = scope._kwargs.get("model", "llama3.2-3b")

    # Calculate tokens using input prompt and aggregated response
    if is_stream:
        input_tokens = general_tokens(prompt)
        output_tokens = general_tokens(scope._llmresponse)
    else:
        input_tokens = scope._input_tokens
        output_tokens = scope._output_tokens

    cost = get_chat_model_cost(request_model, pricing_info, input_tokens, output_tokens)

    # Common Span Attributes
    common_span_attributes(
        scope,
        SemanticConvention.GEN_AI_OPERATION_TYPE_CHAT,
        SemanticConvention.GEN_AI_SYSTEM_PREMAI,
        scope._server_address,
        scope._server_port,
        request_model,
        scope._response_model,
        environment,
        application_name,
        is_stream,
        scope._tbt,
        scope._ttft,
        version,
    )

    # Span Attributes for Response parameters
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_RESPONSE_FINISH_REASON, [scope._finish_reason]
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_SEED, scope._kwargs.get("seed", "")
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_FREQUENCY_PENALTY,
        scope._kwargs.get("frequency_penalty", 0.0),
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_MAX_TOKENS,
        scope._kwargs.get("max_tokens", -1),
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_PRESENCE_PENALTY,
        scope._kwargs.get("presence_penalty", 0.0),
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_STOP_SEQUENCES, scope._kwargs.get("stop", [])
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_TEMPERATURE,
        scope._kwargs.get("temperature", 1.0),
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_TOP_P, scope._kwargs.get("top_p", 1.0)
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_USER, scope._kwargs.get("user", "")
    )
    scope._span.set_attribute(SemanticConvention.GEN_AI_RESPONSE_ID, scope._response_id)
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_OUTPUT_TYPE,
        "text" if isinstance(scope._llmresponse, str) else "json",
    )

    # Span Attributes for Cost and Tokens
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_USAGE_INPUT_TOKENS, input_tokens
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_USAGE_OUTPUT_TOKENS, output_tokens
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_CLIENT_TOKEN_USAGE, input_tokens + output_tokens
    )
    scope._span.set_attribute(SemanticConvention.GEN_AI_USAGE_COST, cost)

    # Span Attributes for Tools
    if scope._tools:
        scope._span.set_attribute(
            SemanticConvention.GEN_AI_TOOL_NAME, scope._tools.get("function", "")
        ).get("name", "")
        scope._span.set_attribute(
            SemanticConvention.GEN_AI_TOOL_CALL_ID, str(scope._tools.get("id", ""))
        )
        scope._span.set_attribute(
            SemanticConvention.GEN_AI_TOOL_ARGS,
            str(scope._tools.get("function", "").get("arguments", "")),
        )

    # Span Attributes for Content
    if capture_message_content:
        scope._span.set_attribute(SemanticConvention.GEN_AI_CONTENT_PROMPT, prompt)
        scope._span.set_attribute(
            SemanticConvention.GEN_AI_CONTENT_COMPLETION, scope._llmresponse
        )

        # To be removed one the change to span_attributes (from span events) is complete
        scope._span.add_event(
            name=SemanticConvention.GEN_AI_CONTENT_PROMPT_EVENT,
            attributes={
                SemanticConvention.GEN_AI_CONTENT_PROMPT: prompt,
            },
        )
        scope._span.add_event(
            name=SemanticConvention.GEN_AI_CONTENT_COMPLETION_EVENT,
            attributes={
                SemanticConvention.GEN_AI_CONTENT_COMPLETION: scope._llmresponse,
            },
        )

    scope._span.set_status(Status(StatusCode.OK))

    # Metrics
    if not disable_metrics:
        record_completion_metrics(
            metrics,
            SemanticConvention.GEN_AI_OPERATION_TYPE_CHAT,
            SemanticConvention.GEN_AI_SYSTEM_PREMAI,
            scope._server_address,
            scope._server_port,
            request_model,
            scope._response_model,
            environment,
            application_name,
            scope._start_time,
            scope._end_time,
            input_tokens,
            output_tokens,
            cost,
            scope._tbt,
            scope._ttft,
        )


def common_embedding_logic(
    scope,
    pricing_info,
    environment,
    application_name,
    metrics,
    capture_message_content,
    disable_metrics,
    version,
):
    """
    Process embedding request and generate Telemetry
    """

    request_model = scope._kwargs.get("model", "text-embedding-ada-002")

    cost = get_embed_model_cost(request_model, pricing_info, scope._input_tokens)

    # Common Span Attributes
    common_span_attributes(
        scope,
        SemanticConvention.GEN_AI_OPERATION_TYPE_EMBEDDING,
        SemanticConvention.GEN_AI_SYSTEM_PREMAI,
        scope._server_address,
        scope._server_port,
        request_model,
        scope._response_model,
        environment,
        application_name,
        False,
        scope._tbt,
        scope._ttft,
        version,
    )

    # Embedding-specific span attributes
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_ENCODING_FORMATS,
        [scope._kwargs.get("encoding_format", "float")],
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_REQUEST_USER, scope._kwargs.get("user", "")
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_USAGE_INPUT_TOKENS, scope._input_tokens
    )
    scope._span.set_attribute(
        SemanticConvention.GEN_AI_CLIENT_TOKEN_USAGE, scope._input_tokens
    )
    scope._span.set_attribute(SemanticConvention.GEN_AI_USAGE_COST, cost)

    # Span Attributes for Content
    if capture_message_content:
        scope._span.add_event(
            name=SemanticConvention.GEN_AI_CONTENT_PROMPT_EVENT,
            attributes={
                SemanticConvention.GEN_AI_CONTENT_PROMPT: str(
                    scope._kwargs.get("input", "")
                ),
            },
        )

    scope._span.set_status(Status(StatusCode.OK))

    # Metrics
    if not disable_metrics:
        record_embedding_metrics(
            metrics,
            SemanticConvention.GEN_AI_OPERATION_TYPE_EMBEDDING,
            SemanticConvention.GEN_AI_SYSTEM_PREMAI,
            scope._server_address,
            scope._server_port,
            request_model,
            scope._response_model,
            environment,
            application_name,
            scope._start_time,
            scope._end_time,
            scope._input_tokens,
            cost,
        )


def process_streaming_chat_response(
    scope,
    pricing_info,
    environment,
    application_name,
    metrics,
    capture_message_content=False,
    disable_metrics=False,
    version="",
):
    """
    Process chat request and generate Telemetry
    """
    common_chat_logic(
        scope,
        pricing_info,
        environment,
        application_name,
        metrics,
        capture_message_content,
        disable_metrics,
        version,
        is_stream=True,
    )


def process_chat_response(
    response,
    request_model,
    pricing_info,
    server_port,
    server_address,
    environment,
    application_name,
    metrics,
    start_time,
    span,
    capture_message_content=False,
    disable_metrics=False,
    version="1.0.0",
    **kwargs,
):
    """
    Process chat request and generate Telemetry
    """

    scope = type("GenericScope", (), {})()
    response_dict = response_as_dict(response)

    scope._start_time = start_time
    scope._end_time = time.time()
    scope._span = span
    scope._llmresponse = str(
        response_dict.get("choices")[0].get("message").get("content")
    )
    scope._response_id = response_dict.get("additional_properties", {}).get("id")
    scope._response_model = response_dict.get("model")
    scope._input_tokens = response_dict.get("usage").get("prompt_tokens")
    scope._output_tokens = response_dict.get("usage").get("completion_tokens")
    scope._timestamps = []
    scope._ttft, scope._tbt = scope._end_time - scope._start_time, 0
    scope._server_address, scope._server_port = server_address, server_port
    scope._kwargs = kwargs
    scope._finish_reason = str(response_dict.get("choices")[0].get("finish_reason"))

    if scope._kwargs.get("tools"):
        scope._tools = response_dict.get("choices")[0].get("message").get("tool_calls")
    else:
        scope._tools = None

    common_chat_logic(
        scope,
        pricing_info,
        environment,
        application_name,
        metrics,
        capture_message_content,
        disable_metrics,
        version,
        is_stream=False,
    )

    return response


def process_embedding_response(
    response,
    request_model,
    pricing_info,
    server_port,
    server_address,
    environment,
    application_name,
    metrics,
    start_time,
    span,
    capture_message_content=False,
    disable_metrics=False,
    version="1.0.0",
    **kwargs,
):
    """
    Process embedding request and generate Telemetry
    """

    scope = type("GenericScope", (), {})()
    response_dict = response_as_dict(response)

    scope._start_time = start_time
    scope._end_time = time.time()
    scope._span = span
    scope._response_model = response_dict.get("model")
    scope._input_tokens = response_dict.get("usage").get("prompt_tokens")
    scope._timestamps = []
    scope._ttft, scope._tbt = scope._end_time - scope._start_time, 0
    scope._server_address, scope._server_port = server_address, server_port
    scope._kwargs = kwargs

    common_embedding_logic(
        scope,
        pricing_info,
        environment,
        application_name,
        metrics,
        capture_message_content,
        disable_metrics,
        version,
    )

    return response
