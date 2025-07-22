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

            # Execute nodes until we reach an end node or no more nodes
            final_result = None
            max_iterations = 10  # Prevent infinite loops
            
            for iteration in range(max_iterations):
                is_first_visit = context.current_node_id != current_node["id"]

                node_type = current_node.get("type") or current_node.get("data", {}).get("type")
                quick_replies = current_node.get("data", {}).get("quick_replies", [])

                is_message_with_quick_replies = (node_type == "message" and quick_replies)
                if is_message_with_quick_replies and is_first_visit:
                    result = await self._execute_message_node(flow, current_node, "", context)
                    if result.success and result.variables_updated:
                        context.variables.update(result.variables_updated)
                    context.history.append({
                        "timestamp": datetime.now().isoformat(),
                        "node_id": current_node["id"],
                        "user_message": "",  # No user message on first visit
                        "bot_response": result.response_message,
                        "variables": result.variables_updated
                    })
                    if result.response_message:
                        final_result = result
                        context.current_node_id = current_node["id"]
                        return final_result if final_result else result
                    context.current_node_id = current_node["id"]
                    # If no response, continue to next node if possible
                    if result.next_node_id and result.next_node_id != current_node["id"]:
                        next_node = next((node for node in flow.nodes if node["id"] == result.next_node_id), None)
                        if next_node:
                            current_node = next_node
                            context.current_node_id = next_node["id"]
                            # If the next node is a message node, clear user_message
                            next_node_type = next_node.get("type") or next_node.get("data", {}).get("type")
                            if next_node_type == "message":
                                user_message = ""
                            continue
                    break

                # Special handling for start node: ignore user_message for transition
                if node_type == "start":
                    result = await self._execute_start_node(flow, current_node, context)
                else:
                    result = await self._execute_node(flow, current_node, user_message, context)

                if result.success and result.variables_updated:
                    context.variables.update(result.variables_updated)
                context.history.append({
                    "timestamp": datetime.now().isoformat(),
                    "node_id": current_node["id"],
                    "user_message": user_message,
                    "bot_response": result.response_message,
                    "variables": result.variables_updated
                })
                if result.response_message:
                    final_result = result
                    context.current_node_id = current_node["id"]
                    break

                # If no response, but there is a next node, continue
                if result.next_node_id and result.next_node_id != current_node["id"]:
                    next_node = next((node for node in flow.nodes if node["id"] == result.next_node_id), None)
                    if next_node:
                        # Clear user_message when moving to message nodes (not just with quick replies)
                        next_node_type = next_node.get("type") or next_node.get("data", {}).get("type")
                        if next_node_type == "message":
                            user_message = ""
                        current_node = next_node
                        context.current_node_id = next_node["id"]
                        continue
                    else:
                        break
                else:
                    context.current_node_id = current_node["id"]
                    break

            # Return the final result with a response message, or the last result
            if final_result:
                return final_result
            elif result:
                return result
            else:
                return FlowExecutionResult(
                    success=False,
                    error_message="No response generated from flow"
                )

        except Exception as e:
            print(f"Flow execution error: {e}")
            import traceback
            traceback.print_exc()
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
            user_message: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """
        Execute a specific node based on its type.
        """
        # Check both node.type and node.data.type
        node_type = node.get("type") or node.get("data", {}).get("type")
        node_data = node.get("data", {})

        if node_type == "start":
            return await self._execute_start_node(flow, node, context)
        elif node_type == "message":
            return await self._execute_message_node(flow, node, user_message, context)
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
            response_message=None  # Start node should not send a message
        )

    async def _execute_message_node(
            self,
            flow: Flow,
            node: Dict[str, Any],
            user_message: str,
            context: FlowExecutionContext
    ) -> FlowExecutionResult:
        """Execute message node - send message to user."""
        node_data = node.get("data", {})
        message = self._interpolate_variables(node_data.get("content", ""), context.variables)
        quick_replies = node_data.get("quick_replies", [])
        delay = node_data.get("delay", 0)
        if delay > 0:
            await asyncio.sleep(delay / 1000)

        if not user_message:
            return FlowExecutionResult(
                success=True,
                next_node_id=node["id"],
                response_message=message,
                quick_replies=quick_replies if quick_replies else None
            )

        next_node_id = self._find_next_node(flow, node["id"], user_message)
        if next_node_id:
            return FlowExecutionResult(
                success=True,
                next_node_id=next_node_id,
                response_message=None,
                quick_replies=None
            )
        else:
            # No match: stay on the same node and notify the user
            notify_msg = "Sorry, I didn't understand your response. Please try again."
            return FlowExecutionResult(
                success=True,
                next_node_id=node["id"],
                response_message=notify_msg,
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

        print(f"Evaluating condition: {condition_type} '{condition_value}' against '{user_message}'")

        # Interpolate variables in condition value
        condition_value = self._interpolate_variables(condition_value, context.variables)

        # Evaluate condition
        condition_met = self._evaluate_condition(user_message, condition_type, condition_value)
        print(f"Condition result: {condition_met}")

        # Find appropriate next node based on condition result
        next_node_id = self._find_conditional_next_node(flow, node["id"], condition_met)
        print(f"Next node after condition: {next_node_id}")

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
            actions_performed.append("Email sent")

        elif action_type == "log_event":
            actions_performed.append("Event logged")

        elif action_type == "transfer_human":
            actions_performed.append("Transferred to human agent")

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

            # Create HTTP client if not exists
            if self.http_client is None:
                timeout = aiohttp.ClientTimeout(total=30)
                self.http_client = aiohttp.ClientSession(timeout=timeout)

            # Make HTTP request with retries
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

                    # Parse response
                    variables_updated = {}
                    response_message = None

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

                except (aiohttp.ClientError, aiohttp.ClientResponseError) as e:
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

    def _find_next_node(self, flow: Flow, current_node_id: str, user_message: str = None) -> Optional[str]:
        """Find the next node in the flow based on user message or quick reply, with strict matching and similarity threshold."""
        edges = [edge for edge in flow.edges if edge["source"] == current_node_id]
        if not edges:
            return None

        if user_message:
            user_message_lower = user_message.lower().strip()
            # 1. Exact match (case-insensitive)
            for edge in edges:
                edge_label = edge.get("label", "").lower().strip()
                if edge_label and edge_label == user_message_lower:
                    return edge["target"]

            # 2. Similarity match (above threshold)
            best_match = None
            best_score = 0.0
            for edge in edges:
                edge_label = edge.get("label", "").lower().strip()
                if edge_label:
                    score = self._calculate_similarity(user_message_lower, edge_label)
                    if score > best_score:
                        best_score = score
                        best_match = edge
            if best_match and best_score >= 0.7:
                return best_match["target"]

            # 3. No match: return None to indicate staying on the same node
            return None

        # For start nodes or non-interactive transitions, always return the first outgoing edge's target (if any)
        return edges[0]["target"] if edges else None

    def _find_conditional_next_node(
            self,
            flow: Flow,
            current_node_id: str,
            condition_met: bool
    ) -> Optional[str]:
        """Find next node based on condition result."""
        print(f"Finding conditional next node for {current_node_id}, condition_met: {condition_met}")
        
        # Look for edges with conditions
        for edge in flow.edges:
            if edge["source"] == current_node_id:
                edge_condition = edge.get("condition")
                edge_label = edge.get("label", "No label")
                print(f"Checking edge: {edge['source']} -> {edge['target']} (label: {edge_label}, condition: {edge_condition})")
                
                if edge_condition:
                    if (condition_met and edge_condition.lower() in ["true", "yes", "1"]) or \
                            (not condition_met and edge_condition.lower() in ["false", "no", "0"]):
                        print(f"Conditional edge matched: {edge['target']}")
                        return edge["target"]
                else:
                    # Default edge (no condition) - use label to determine routing
                    if edge_label.lower() in ["not services", "not support", "not about", "default"]:
                        if not condition_met:
                            print(f"Default edge matched (condition not met): {edge['target']}")
                            return edge["target"]
                    elif condition_met:
                        print(f"Default edge matched (condition met): {edge['target']}")
                        return edge["target"]

        # If no conditional edge found, return first available edge
        default_next = self._find_next_node(flow, current_node_id)
        print(f"No conditional edge found, using default: {default_next}")
        return default_next

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
