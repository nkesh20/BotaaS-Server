import json
import re
import asyncio
import aiohttp
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
        self.http_client = None  # Will be created when needed

    async def execute_flow(
            self,
            flow_id: int,
            input: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """
        Execute a flow with the given input and context.
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

            final_result = FlowExecutionResult(
                    success=False,
                    error_message="No response generated from flow"
                )

            max_iterations = 10  # Prevent infinite loops
            for _ in range(max_iterations):
                is_first_visit = context.current_node_id != current_node["id"]
                context.current_node_id = current_node["id"]

                result = await self._execute_node(flow, current_node, input, context, is_first_visit)
                if result is None:
                    break

                self._update_context_and_history(context, current_node, result, input)
                final_result = result

                if result.next_node_id == context.current_node_id:
                    break
                elif result.next_node_id:
                    current_node = next((node for node in flow.nodes if node["id"] == result.next_node_id), None)
                    if current_node:
                        # if result.output is not None, use it as input
                        input = result.output if result.output else ""
                        continue
                break
            
            return final_result

        except Exception as e:
            print(f"Flow execution error: {e}")
            import traceback
            traceback.print_exc()
            return FlowExecutionResult(
                success=False,
                error_message=f"Flow execution error: {str(e)}"
            )

    def _update_context_and_history(self, context, current_node, result, input):
        if result.success and result.variables_updated:
            context.variables.update(result.variables_updated)
        context.history.append({
            "timestamp": datetime.now().isoformat(),
            "node_id": current_node["id"],
            "input": input,
            "bot_response": result.response_message,
            "variables": result.variables_updated
        })

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
            # Check both node.type and node.data.type
            node_type = node.get("type") or node.get("data", {}).get("type")
            if node_type == "start":
                return node

        # If no start node, return first node
        first_node = flow.nodes[0] if flow.nodes else None
        return first_node

    async def _execute_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            input: str,
            context: FlowExecutionContext,
            is_first_visit: bool = False
    ) -> FlowExecutionResult:
        """
        Execute a specific node based on its type.
        """
        node_type = node.get("type") or node.get("data", {}).get("type")
        node_data = node.get("data", {})

        if node_type == "start":
            return await self._execute_start_node(flow, node, context)
        elif node_type == "message":
            return await self._execute_message_node(flow, node, input, context, is_first_visit=is_first_visit)
        elif node_type == "condition":
            return await self._execute_condition_node(flow, node, input, context)
        elif node_type == "action":
            return await self._execute_action_node(flow, node, context)
        elif node_type == "webhook":
            return await self._execute_webhook_node(flow, node, input, context)
        elif node_type == "input":
            return await self._execute_input_node(flow, node, input, context, is_first_visit=is_first_visit)
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
        """Execute start node - always move to the first outgoing edge, ignoring label and user_message."""
        next_node_id = self._find_next_node(flow, node["id"])
        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            output=None,
            response_message=None  # Start node should not send a message
        )

    async def _execute_message_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            input: str,
            context: FlowExecutionContext,
            is_first_visit: bool = False
    ) -> FlowExecutionResult:
        """
        Execute message node - send message to user. Handles both first visit and regular cases.
        """
        node_data = node.get("data", {})
        message = self._interpolate_variables(node_data.get("content", ""), context.variables)
        quick_replies = node_data.get("quick_replies", [])
        delay = node_data.get("delay", 0)
        if delay > 0:
            await asyncio.sleep(delay / 1000)

        if is_first_visit:
            result = FlowExecutionResult(
                success=True,
                next_node_id=node["id"],
                response_message=message,
                quick_replies=quick_replies if quick_replies else None
            )
            if result.success and result.variables_updated:
                context.variables.update(result.variables_updated)
            return result

        if not input:
            return FlowExecutionResult(
                success=True,
                next_node_id=node["id"],
                response_message=message,
                quick_replies=quick_replies if quick_replies else None
            )

        next_node_id = self._find_next_node(flow, node["id"], input)
        if next_node_id:
            return FlowExecutionResult(
                success=True,
                next_node_id=next_node_id,
                output=input,
                response_message=None,
                quick_replies=None
            )
        else:
            return FlowExecutionResult(
                success=True,
                next_node_id=node["id"],
                output=input,
                response_message="I couldn't understand your message. Please try again.",
                quick_replies=quick_replies if quick_replies else None
            )

    async def _execute_condition_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            input: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """
        Execute condition node - evaluate condition and route accordingly.
        """
        node_data = node.get("data", {})
        condition_type = node_data.get("condition_type", "equals")
        condition_value = node_data.get("condition_value", "")

        print(f"Evaluating condition: {condition_type} '{condition_value}' against '{input}'")

        condition_value = self._interpolate_variables(condition_value, context.variables)
        condition_met = self._evaluate_condition(input, condition_type, condition_value)
        print(f"Condition result: {condition_met}")

        output = "true" if condition_met else "false"
        next_node_id = self._find_next_node(flow, node["id"], output)
        print(f"Next node after condition: {next_node_id}")

        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            output=output,
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

        output = None
        if action_type == "set_variable":
            variable_name = params.get("variable")
            variable_value = params.get("value")
            if variable_name:
                output = variable_value
                variables_updated[variable_name] = variable_value
                actions_performed.append(f"Set variable {variable_name} = {variable_value}")

        elif action_type == "send_email":
            actions_performed.append("Email sent")

        elif action_type == "log_event":
            actions_performed.append("Event logged")

        elif action_type == "transfer_human":
            actions_performed.append("Transferred to human agent")

        next_node_id = self._find_next_node(flow, node["id"], output)

        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            output=output,
            variables_updated=variables_updated,
            actions_performed=actions_performed
        )

    async def _execute_webhook_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            input: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """
        Execute webhook node - make HTTP request to external service.
        """
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
            try:
                headers_dict = json.loads(headers)
            except json.JSONDecodeError:
                headers_dict = {}

            if request_body.strip():
                try:
                    body_dict = json.loads(request_body)
                    body_dict = self._interpolate_dict_variables(body_dict, context.variables)

                    webhook_payload = WebhookPayload(
                        user_id=context.user_id,
                        session_id=context.session_id,
                        message=input,
                        variables=context.variables,
                        flow_id=flow.id,
                        node_id=node["id"]
                    )

                    body_dict.update(webhook_payload.model_dump())
                    request_body = json.dumps(body_dict, default=str)
                except json.JSONDecodeError:
                    request_body = self._interpolate_variables(request_body, context.variables)

            if self.http_client is None:
                timeout = aiohttp.ClientTimeout(total=30)
                self.http_client = aiohttp.ClientSession(timeout=timeout)

            for attempt in range(retry_count + 1):
                try:
                    if method == "GET":
                        async with self.http_client.get(webhook_url, headers=headers_dict) as response:
                            response.raise_for_status()
                            response_data = await response.json() if response.headers.get("content-type", "").startswith("application/json") else None
                    elif method == "POST":
                        async with self.http_client.post(
                            webhook_url,
                            headers=headers_dict,
                            data=request_body
                        ) as response:
                            response.raise_for_status()
                            response_data = await response.json() if response.headers.get("content-type", "").startswith("application/json") else None
                    elif method == "PUT":
                        async with self.http_client.put(
                            webhook_url,
                            headers=headers_dict,
                            data=request_body
                        ) as response:
                            response.raise_for_status()
                            response_data = await response.json() if response.headers.get("content-type", "").startswith("application/json") else None
                    elif method == "DELETE":
                        async with self.http_client.delete(webhook_url, headers=headers_dict) as response:
                            response.raise_for_status()
                            response_data = await response.json() if response.headers.get("content-type", "").startswith("application/json") else None
                    else:
                        return FlowExecutionResult(
                            success=False,
                            error_message=f"Unsupported HTTP method: {method}"
                        )

                    variables_updated = {}
                    response_message = None

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

                except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
                    if attempt == retry_count:
                        return FlowExecutionResult(
                            success=False,
                            error_message=f"Webhook request failed: {str(e)}"
                        )
                    await asyncio.sleep(1)

        except Exception as e:
            return FlowExecutionResult(
                success=False,
                error_message=f"Webhook execution error: {str(e)}"
            )

    async def _execute_input_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            input: str,
            context: FlowExecutionContext,
            is_first_visit: bool = False
    ) -> FlowExecutionResult:
        """
        Execute input node - wait for input on first visit, assign result to input for edge selection without validation.
        """
        node_data = node.get("data", {})
        input_type = node_data.get("input_type", "text")
        variable_name = node_data.get("variable_name")
        prompt_message = node_data.get("prompt") or node_data.get("content") or "Please provide input."

        if not variable_name:
            return FlowExecutionResult(
                success=False,
                error_message="Variable name not specified for input node"
            )

        if is_first_visit:
            return FlowExecutionResult(
                success=True,
                next_node_id=node["id"],
                response_message=prompt_message
            )

        # No validation or conversion, just store the input as-is
        variables_updated = {variable_name: input}
        next_node_id = self._find_next_node(flow, node["id"], input)
        return FlowExecutionResult(
            success=True,
            next_node_id=next_node_id,
            output=input,
            response_message=None,
            variables_updated=variables_updated,
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

    def _find_next_node(self, flow: Flow, current_node_id: str, input: str = None) -> Optional[str]:
        """
        Find the next node in the flow based on input and edge conditions.
        - If an edge's condition is empty, select and return its target immediately (first such edge).
        - If not, look for an exact match (case-insensitive, trimmed) between input and condition (first such edge).
        - If not, look for the best similarity above 0.7 between input and condition.
        - If none match, return None.
        """
        edges = [edge for edge in flow.edges if edge["source"] == current_node_id]
        if not edges:
            return None

        input_str = str(input).lower().strip() if input is not None else ""

        best_match = None
        best_score = 0.0
        for edge in edges:
            condition = edge.get("condition", "")
            if not condition:
                return edge["target"]
            condition = condition.lower().strip()
            if input_str == condition:
                return edge["target"]
            else:
                score = self._calculate_similarity(input_str, condition)
                if score > best_score:
                    best_score = score
                    best_match = edge
            
        if best_match and best_score >= 0.7:
            return best_match["target"]

        return None

    def _evaluate_condition(self, input: str, condition_type: str, condition_value: str) -> bool:
        """
        Evaluate a condition against input.
        Supported types: equals, contains, number, email, phone_number, date, regex
        """
        input_str = input.strip()
        condition_value_str = condition_value.strip()

        if condition_type == "equals":
            return input_str.lower() == condition_value_str.lower()
        elif condition_type == "contains":
            return condition_value_str.lower() in input_str.lower()
        elif condition_type == "regex":
            try:
                return bool(re.search(condition_value_str, input_str, re.IGNORECASE))
            except re.error:
                return False
        elif condition_type == "number":
            try:
                input_num = float(input_str)
                if condition_value_str:
                    cond_num = float(condition_value_str)
                    return input_num == cond_num
                return True  # Just check if input is a number
            except ValueError:
                return False
        elif condition_type == "email":
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'
            return bool(re.match(email_pattern, input_str))
        elif condition_type == "phone_number":
            phone_pattern = r'^\\+?[\\d\\s\\-\\(\\)]{10,}$'
            return bool(re.match(phone_pattern, input_str))
        elif condition_type == "date":
            # Accepts YYYY-MM-DD, MM/DD/YYYY, MM-DD-YYYY
            date_patterns = [
                r'^\d{4}-\d{2}-\d{2}$',
                r'^\d{2}/\d{2}/\d{4}$',
                r'^\d{2}-\d{2}-\d{4}$'
            ]
            input_str = input_str.strip()
            return any(re.fullmatch(pattern, input_str) for pattern in date_patterns)
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
        """Close the HTTP client."""
        if self.http_client:
            await self.http_client.close()

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two strings using simple algorithms."""
        if not text1 or not text2:
            return 0.0
        
        # Simple similarity calculation
        # Check if words are similar (for quick reply matching)
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        jaccard_similarity = intersection / union
        
        # Also check character-level similarity for short strings
        if len(text1) <= 20 and len(text2) <= 20:
            # For short strings, also consider character-level similarity
            char_similarity = self._levenshtein_similarity(text1, text2)
            return max(jaccard_similarity, char_similarity)
        
        return jaccard_similarity
    
    def _levenshtein_similarity(self, text1: str, text2: str) -> float:
        """Calculate Levenshtein distance-based similarity."""
        if not text1 or not text2:
            return 0.0
        
        # Simple Levenshtein distance calculation
        len1, len2 = len(text1), len(text2)
        if len1 == 0:
            return 0.0
        if len2 == 0:
            return 0.0
        
        # Create matrix
        matrix = [[0] * (len2 + 1) for _ in range(len1 + 1)]
        
        # Initialize first row and column
        for i in range(len1 + 1):
            matrix[i][0] = i
        for j in range(len2 + 1):
            matrix[0][j] = j
        
        # Fill matrix
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if text1[i-1] == text2[j-1]:
                    matrix[i][j] = matrix[i-1][j-1]
                else:
                    matrix[i][j] = min(
                        matrix[i-1][j] + 1,      # deletion
                        matrix[i][j-1] + 1,      # insertion
                        matrix[i-1][j-1] + 1     # substitution
                    )
        
        # Calculate similarity (1 - normalized distance)
        max_len = max(len1, len2)
        if max_len == 0:
            return 1.0
        
        distance = matrix[len1][len2]
        similarity = 1.0 - (distance / max_len)
        return similarity
