# pylint: disable=duplicate-code, broad-exception-caught, too-many-statements, unused-argument
"""
Module for monitoring EmbedChain applications.
"""

import logging
from opentelemetry.trace import SpanKind, Status, StatusCode
from opentelemetry.sdk.resources import (
    SERVICE_NAME,
    TELEMETRY_SDK_NAME,
    DEPLOYMENT_ENVIRONMENT,
)
from openlit.__helpers import handle_exception
from openlit.semcov import SemanticConvention

# Initialize logger for logging potential issues and operations
logger = logging.getLogger(__name__)


def evaluate(
    gen_ai_endpoint,
    version,
    environment,
    application_name,
    tracer,
    pricing_info,
    capture_message_content,
):
    """
    Creates a wrapper around a function call to trace and log its execution metrics.

    This function wraps any given function to measure its execution time,
    log its operation, and trace its execution using OpenTelemetry.

    Parameters:
    - gen_ai_endpoint (str): A descriptor or name for the endpoint being traced.
    - version (str): The version of the EmbedChain application.
    - environment (str): The deployment environment (e.g., 'production', 'development').
    - application_name (str): Name of the EmbedChain application.
    - tracer (opentelemetry.trace.Tracer): The tracer object used for OpenTelemetry tracing.
    - pricing_info (dict): Information about the pricing for internal metrics (currently not used).
    - capture_message_content (bool): Flag indicating whether to trace the content of the response.

    Returns:
    - function: A higher-order function that takes a function 'wrapped' and returns
                a new function that wraps 'wrapped' with additional tracing and logging.
    """

    def wrapper(wrapped, instance, args, kwargs):
        """
        An inner wrapper function that executes the wrapped function, measures execution
        time, and records trace data using OpenTelemetry.

        Parameters:
        - wrapped (Callable): The original function that this wrapper will execute.
        - instance (object): The instance to which the wrapped function belongs. This
                             is used for instance methods. For static and classmethods,
                             this may be None.
        - args (tuple): Positional arguments passed to the wrapped function.
        - kwargs (dict): Keyword arguments passed to the wrapped function.

        Returns:
        - The result of the wrapped function call.

        The wrapper initiates a span with the provided tracer, sets various attributes
        on the span based on the function's execution and response, and ensures
        errors are handled and logged appropriately.
        """
        with tracer.start_as_current_span(
            gen_ai_endpoint, kind=SpanKind.CLIENT
        ) as span:
            response = wrapped(*args, **kwargs)

            try:
                span.set_attribute(TELEMETRY_SDK_NAME, "openlit")
                span.set_attribute(
                    SemanticConvention.GEN_AI_SYSTEM,
                    SemanticConvention.GEN_AI_SYSTEM_EMBEDCHAIN,
                )
                span.set_attribute(SemanticConvention.GEN_AI_ENDPOINT, gen_ai_endpoint)
                span.set_attribute(DEPLOYMENT_ENVIRONMENT, environment)
                span.set_attribute(
                    SemanticConvention.GEN_AI_OPERATION,
                    SemanticConvention.GEN_AI_OPERATION_TYPE_FRAMEWORK,
                )
                span.set_attribute(SERVICE_NAME, application_name)
                span.set_attribute(
                    SemanticConvention.GEN_AI_EVAL_CONTEXT_RELEVANCY,
                    response["context_relevancy"],
                )
                span.set_attribute(
                    SemanticConvention.GEN_AI_EVAL_ANSWER_RELEVANCY,
                    response["answer_relevancy"],
                )
                span.set_attribute(
                    SemanticConvention.GEN_AI_EVAL_GROUNDEDNESS,
                    response["groundedness"],
                )

                span.set_status(Status(StatusCode.OK))

                # Return original response
                return response

            except Exception as e:
                handle_exception(span, e)
                logger.error("Error in trace creation: %s", e)

                # Return original response
                return response

    return wrapper


def get_data_sources(
    gen_ai_endpoint,
    version,
    environment,
    application_name,
    tracer,
    pricing_info,
    capture_message_content,
):
    """
    Creates a wrapper around a function call to trace and log its execution metrics.

    This function wraps any given function to measure its execution time,
    log its operation, and trace its execution using OpenTelemetry.

    Parameters:
    - gen_ai_endpoint (str): A descriptor or name for the endpoint being traced.
    - version (str): The version of the EmbedChain application.
    - environment (str): The deployment environment (e.g., 'production', 'development').
    - application_name (str): Name of the EmbedChain application.
    - tracer (opentelemetry.trace.Tracer): The tracer object used for OpenTelemetry tracing.
    - pricing_info (dict): Information about the pricing for internal metrics (currently not used).
    - capture_message_content (bool): Flag indicating whether to trace the content of the response.

    Returns:
    - function: A higher-order function that takes a function 'wrapped' and returns
                a new function that wraps 'wrapped' with additional tracing and logging.
    """

    def wrapper(wrapped, instance, args, kwargs):
        """
        An inner wrapper function that executes the wrapped function, measures execution
        time, and records trace data using OpenTelemetry.

        Parameters:
        - wrapped (Callable): The original function that this wrapper will execute.
        - instance (object): The instance to which the wrapped function belongs. This
                             is used for instance methods. For static and classmethods,
                             this may be None.
        - args (tuple): Positional arguments passed to the wrapped function.
        - kwargs (dict): Keyword arguments passed to the wrapped function.

        Returns:
        - The result of the wrapped function call.

        The wrapper initiates a span with the provided tracer, sets various attributes
        on the span based on the function's execution and response, and ensures
        errors are handled and logged appropriately.
        """
        with tracer.start_as_current_span(
            gen_ai_endpoint, kind=SpanKind.CLIENT
        ) as span:
            response = wrapped(*args, **kwargs)

            try:
                span.set_attribute(TELEMETRY_SDK_NAME, "openlit")
                span.set_attribute(
                    SemanticConvention.GEN_AI_SYSTEM,
                    SemanticConvention.GEN_AI_SYSTEM_EMBEDCHAIN,
                )
                span.set_attribute(SemanticConvention.GEN_AI_ENDPOINT, gen_ai_endpoint)
                span.set_attribute(DEPLOYMENT_ENVIRONMENT, environment)
                span.set_attribute(
                    SemanticConvention.GEN_AI_OPERATION,
                    SemanticConvention.GEN_AI_OPERATION_TYPE_FRAMEWORK,
                )
                span.set_attribute(SERVICE_NAME, application_name)
                span.set_attribute(
                    SemanticConvention.GEN_AI_DATA_SOURCES, len(response)
                )

                span.set_status(Status(StatusCode.OK))

                # Return original response
                return response

            except Exception as e:
                handle_exception(span, e)
                logger.error("Error in trace creation: %s", e)

                # Return original response
                return response

    return wrapper
