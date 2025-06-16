import json
import re
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy.orm import Session

from app.models.flow import Flow
from app.schemas.flow import FlowExecutionContext, FlowExecutionResult, WebhookPayload


class FlowEngine:
    """
    Engine for executing conversation flows.
    """

    def __init__(self, db: Session):
        self.db = db
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def execute_flow(
            self,
            flow_id: int,
            user_message: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """
        Execute a flow with the given user message and context.
        """
        try:
            flow = Flow.get_by_id(self.db, flow_id)
            if not flow or not flow.is_active:
                return FlowExecutionResult(
                    success=False,
                    error_message="Flow not found or inactive"
                )

            # Start from current node or find start node
            current_node = self._find_current_node(flow, context)
            if not current_node:
                return FlowExecutionResult(
                    success=False,
                    error_message="No valid starting node found"
                )

            # Execute the current node
            result = await self._execute_node(flow, current_node, user_message, context)

            # Update context with execution result
            if result.success and result.variables_updated:
                context.variables.update(result.variables_updated)

            # Add to history
            context.history.append({
                "timestamp": datetime.now().isoformat(),
                "node_id": current_node["id"],
                "user_message": user_message,
                "bot_response": result.response_message,
                "variables": result.variables_updated
            })

            return result

        except Exception as e:
            return FlowExecutionResult(
                success=False,
                error_message=f"Flow execution error: {str(e)}"
            )

    def _find_current_node(self, flow: Flow, context: FlowExecutionContext) -> Optional[Dict[str, Any]]:
        """
        Find the current node to execute based on context.
        """
        # If context has current_node_id, use it
        if context.current_node_id:
            for node in flow.nodes:
                if node["id"] == context.current_node_id:
                    return node

        # Otherwise, find the start node
        for node in flow.nodes:
            if node.get("type") == "start":
                return node

        # If no start node, return first node
        return flow.nodes[0] if flow.nodes else None

    async def _execute_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            user_message: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """
        Execute a specific node based on its type.
        """
        node_type = node.get("type")
        node_data = node.get("data", {})

        if node_type == "start":
            return await self._execute_start_node(flow, node, context)
        elif node_type == "message":
            return await self._execute_message_node(flow, node, context)
        elif node_type == "condition":
            return await self._execute_condition_node(flow, node, user_message, context)
        elif node_type == "action":
            return await self._execute_action_node(flow, node, context)
        elif node_type == "webhook":
            return await self._execute_webhook_node(flow, node, user_message, context)
        elif node_type == "input":
            return await self._execute_input_node(flow, node, user_message, context)
        elif node_type == "end":
            return await self._execute_end_node(flow, node, context)
        else:
            return FlowExecutionResult(
                success=False,
                error_message=f"Unknown node type: {node_type}"
            )

    async def _execute_start_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute start node - simply move to next node."""
        next_node_id = self._find_next_node(flow, node["id"])
        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            response_message="Flow started"
        )

    async def _execute_message_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute message node - send message to user."""
        node_data = node.get("data", {})
        message = self._interpolate_variables(node_data.get("content", ""), context.variables)
        quick_replies = node_data.get("quick_replies", [])

        # Add delay if specified
        delay = node_data.get("delay", 0)
        if delay > 0:
            await asyncio.sleep(delay / 1000)  # Convert ms to seconds

        next_node_id = self._find_next_node(flow, node["id"])

        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            response_message=message,
            quick_replies=quick_replies if quick_replies else None
        )

    async def _execute_condition_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            user_message: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute condition node - evaluate condition and route accordingly."""
        node_data = node.get("data", {})
        condition_type = node_data.get("condition_type", "equals")
        condition_value = node_data.get("condition_value", "")

        # Interpolate variables in condition value
        condition_value = self._interpolate_variables(condition_value, context.variables)

        # Evaluate condition
        condition_met = self._evaluate_condition(user_message, condition_type, condition_value)

        # Find appropriate next node based on condition result
        next_node_id = self._find_conditional_next_node(flow, node["id"], condition_met)

        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            variables_updated={"last_condition_result": condition_met}
        )

    async def _execute_action_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute action node - perform specified action."""
        node_data = node.get("data", {})
        action_type = node_data.get("action_type")
        action_params = node_data.get("action_params", "{}")

        try:
            params = json.loads(action_params)
        except json.JSONDecodeError:
            params = {}

        # Interpolate variables in parameters
        params = self._interpolate_dict_variables(params, context.variables)

        variables_updated = {}
        actions_performed = []

        if action_type == "set_variable":
            variable_name = params.get("variable")
            variable_value = params.get("value")
            if variable_name:
                variables_updated[variable_name] = variable_value
                actions_performed.append(f"Set variable {variable_name} = {variable_value}")

        elif action_type == "send_email":
            # TODO: Implement email sending
            actions_performed.append("Email sent (not implemented)")

        elif action_type == "log_event":
            # TODO: Implement event logging
            actions_performed.append("Event logged (not implemented)")

        elif action_type == "transfer_human":
            # TODO: Implement human transfer
            actions_performed.append("Transferred to human agent (not implemented)")

        next_node_id = self._find_next_node(flow, node["id"])

        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            variables_updated=variables_updated,
            actions_performed=actions_performed
        )

    async def _execute_webhook_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            user_message: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute webhook node - make HTTP request to external service."""
        node_data = node.get("data", {})
        webhook_url = node_data.get("webhook_url")
        method = node_data.get("method", "POST").upper()
        headers = node_data.get("headers", "{}")
        request_body = node_data.get("request_body", "{}")
        retry_count = node_data.get("retry_count", 0)

        if not webhook_url:
            return FlowExecutionResult(
                success=False,
                error_message="Webhook URL not specified"
            )

        try:
            # Parse headers
            try:
                headers_dict = json.loads(headers)
            except json.JSONDecodeError:
                headers_dict = {}

            # Parse and interpolate request body
            if request_body.strip():
                try:
                    body_dict = json.loads(request_body)
                    body_dict = self._interpolate_dict_variables(body_dict, context.variables)

                    # Add standard webhook payload
                    webhook_payload = WebhookPayload(
                        user_id=context.user_id,
                        session_id=context.session_id,
                        message=user_message,
                        variables=context.variables,
                        flow_id=flow.id,
                        node_id=node["id"]
                    )

                    body_dict.update(webhook_payload.model_dump())
                    request_body = json.dumps(body_dict)
                except json.JSONDecodeError:
                    request_body = self._interpolate_variables(request_body, context.variables)

            # Make HTTP request with retries
            for attempt in range(retry_count + 1):
                try:
                    if method == "GET":
                        response = await self.http_client.get(webhook_url, headers=headers_dict)
                    elif method == "POST":
                        response = await self.http_client.post(
                            webhook_url,
                            headers=headers_dict,
                            content=request_body
                        )
                    elif method == "PUT":
                        response = await self.http_client.put(
                            webhook_url,
                            headers=headers_dict,
                            content=request_body
                        )
                    elif method == "DELETE":
                        response = await self.http_client.delete(webhook_url, headers=headers_dict)
                    else:
                        return FlowExecutionResult(
                            success=False,
                            error_message=f"Unsupported HTTP method: {method}"
                        )

                    response.raise_for_status()

                    # Parse response
                    variables_updated = {}
                    response_message = None

                    if response.headers.get("content-type", "").startswith("application/json"):
                        response_data = response.json()

                        # Extract variables from response
                        if isinstance(response_data, dict):
                            if "variables" in response_data:
                                variables_updated.update(response_data["variables"])
                            if "message" in response_data:
                                response_message = response_data["message"]

                    next_node_id = self._find_next_node(flow, node["id"])

                    return FlowExecutionResult(
                        success=True,
                        next_node_id=next_node_id,
                        response_message=response_message,
                        variables_updated=variables_updated,
                        actions_performed=[f"Webhook {method} request to {webhook_url}"]
                    )

                except httpx.HTTPError as e:
                    if attempt == retry_count:  # Last attempt
                        return FlowExecutionResult(
                            success=False,
                            error_message=f"Webhook request failed: {str(e)}"
                        )
                    await asyncio.sleep(1)  # Wait before retry

        except Exception as e:
            return FlowExecutionResult(
                success=False,
                error_message=f"Webhook execution error: {str(e)}"
            )

    async def _execute_input_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            user_message: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute input node - validate and store user input."""
        node_data = node.get("data", {})
        input_type = node_data.get("input_type", "text")
        variable_name = node_data.get("variable_name")
        validation_pattern = node_data.get("validation_pattern")

        if not variable_name:
            return FlowExecutionResult(
                success=False,
                error_message="Variable name not specified for input node"
            )

        # Validate input based on type
        validation_error = self._validate_input(user_message, input_type, validation_pattern)
        if validation_error:
            return FlowExecutionResult(
                success=False,
                error_message=validation_error,
                next_node_id=node["id"]  # Stay on same node
            )

        # Convert input based on type
        converted_value = self._convert_input(user_message, input_type)

        next_node_id = self._find_next_node(flow, node["id"])

        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            variables_updated={variable_name: converted_value},
            actions_performed=[f"Stored user input in variable {variable_name}"]
        )

    async def _execute_end_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute end node - terminate flow."""
        node_data = node.get("data", {})
        message = node_data.get("content", "Conversation ended")

        return FlowExecutionResult(
            success=True,
            next_node_id=None,  # No next node - flow ends
            response_message=self._interpolate_variables(message, context.variables)
        )

    def _find_next_node(self, flow: Flow, current_node_id: str) -> Optional[str]:
        """Find the next node in the flow."""
        for edge in flow.edges:
            if edge["source"] == current_node_id:
                return edge["target"]
        return None

    def _find_conditional_next_node(
            self,
            flow: Flow,
            current_node_id: str,
            condition_met: bool
    ) -> Optional[str]:
        """Find next node based on condition result."""
        # Look for edges with conditions
        for edge in flow.edges:
            if edge["source"] == current_node_id:
                edge_condition = edge.get("condition")
                if edge_condition:
                    if (condition_met and edge_condition.lower() in ["true", "yes", "1"]) or \
                            (not condition_met and edge_condition.lower() in ["false", "no", "0"]):
                        return edge["target"]
                else:
                    # Default edge (no condition)
                    if not condition_met:
                        return edge["target"]

        # If no conditional edge found, return first available edge
        return self._find_next_node(flow, current_node_id)

    def _evaluate_condition(self, user_message: str, condition_type: str, condition_value: str) -> bool:
        """Evaluate a condition against user message."""
        user_message = user_message.lower().strip()
        condition_value = condition_value.lower().strip()

        if condition_type == "equals":
            return user_message == condition_value
        elif condition_type == "contains":
            return condition_value in user_message
        elif condition_type == "regex":
            try:
                return bool(re.search(condition_value, user_message, re.IGNORECASE))
            except re.error:
                return False
        elif condition_type == "intent":
            # TODO: Implement intent recognition
            return condition_value in user_message
        else:
            return False

    def _validate_input(self, input_value: str, input_type: str, validation_pattern: Optional[str]) -> Optional[str]:
        """Validate user input based on type and pattern."""
        if input_type == "email":
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

            if not re.match(email_pattern, input_value):
                return "Please enter a valid email address"

        elif input_type == "phone":
            phone_pattern = r'^\+?[\d\s\-\(\)]{10,}'

            if not re.match(phone_pattern, input_value):
                return "Please enter a valid phone number"

        elif input_type == "number":
            try:
                float(input_value)
            except ValueError:
                return "Please enter a valid number"

        elif input_type == "date":
            # Basic date validation - you might want to use dateutil for more robust parsing
            date_patterns = [r'^\d{4}-\d{2}-\d{2}'
                , r'^\d{2}/\d{2}/\d{4}'
                , r'^\d{2}-\d{2}-\d{4}'
                             ]
            if not any(re.match(pattern, input_value) for pattern in date_patterns):
                return "Please enter a valid date (YYYY-MM-DD, MM/DD/YYYY, or MM-DD-YYYY)"

        # Custom validation pattern
        if validation_pattern:
            try:
                if not re.match(validation_pattern, input_value):
                    return f"Input does not match required pattern: {validation_pattern}"
            except re.error:
                return "Invalid validation pattern"

        return None

    def _convert_input(self, input_value: str, input_type: str) -> Any:
        """Convert input to appropriate type."""
        if input_type == "number":
            try:
                if '.' in input_value:
                    return float(input_value)
                else:
                    return int(input_value)
            except ValueError:
                return input_value
        else:
            return input_value

    def _interpolate_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """Replace variable placeholders in text with actual values."""
        if not text or not variables:
            return text

        # Replace {{variable_name}} with actual values
        for var_name, var_value in variables.items():
            placeholder = f"{{{{{var_name}}}}}"
            text = text.replace(placeholder, str(var_value))

        return text

    def _interpolate_dict_variables(self, data: Dict[str, Any], variables: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively interpolate variables in dictionary values."""
        if not data or not variables:
            return data

        result = {}
        for key, value in data.items():
            if isinstance(value, str):
                result[key] = self._interpolate_variables(value, variables)
            elif isinstance(value, dict):
                result[key] = self._interpolate_dict_variables(value, variables)
            elif isinstance(value, list):
                result[key] = [
                    self._interpolate_variables(item, variables) if isinstance(item, str) else item
                    for item in value
                ]
            else:
                result[key] = value

        return result

    async def close(self):
        """Close HTTP client."""
        await self.http_client.aclose()
