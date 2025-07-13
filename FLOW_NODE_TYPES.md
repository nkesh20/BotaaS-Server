# Flow Node Types

This document explains the different node types available in the BotaaS flow builder.

## Node Types

### 1. Start Node
- **Purpose**: Entry point of the flow
- **Data**: `{"type": "start"}`
- **Behavior**: Automatically moves to the next connected node
- **Use Case**: Always the first node in a flow

### 2. Message Node
- **Purpose**: Sends a message to the user
- **Data**: 
  ```json
  {
    "type": "message",
    "content": "Your message here",
    "quick_replies": ["Button 1", "Button 2"],
    "delay": 1000
  }
  ```
- **Behavior**: Sends text message with optional quick reply buttons
- **Use Case**: Welcome messages, information responses, menu options

### 3. Condition Node
- **Purpose**: Routes flow based on user input
- **Data**:
  ```json
  {
    "type": "condition",
    "condition_type": "contains|equals|regex",
    "condition_value": "services"
  }
  ```
- **Condition Types**:
  - `contains`: Checks if user message contains the value
  - `equals`: Exact match
  - `regex`: Regular expression match
- **Use Case**: Menu navigation, input validation, branching logic

### 4. Action Node
- **Purpose**: Performs actions like setting variables
- **Data**:
  ```json
  {
    "type": "action",
    "action_type": "set_variable",
    "action_params": "{\"variable\": \"user_name\", \"value\": \"John\"}"
  }
  ```
- **Action Types**:
  - `set_variable`: Store user input in variables
  - `send_email`: Send email (not implemented)
  - `log_event`: Log events (not implemented)
  - `transfer_human`: Transfer to human agent (not implemented)
- **Use Case**: Data collection, variable management

### 5. Webhook Node
- **Purpose**: Makes HTTP requests to external services
- **Data**:
  ```json
  {
    "type": "webhook",
    "webhook_url": "https://api.example.com/webhook",
    "method": "POST",
    "headers": "{\"Authorization\": \"Bearer token\"}",
    "request_body": "{\"message\": \"{{user_message}}\"}"
  }
  ```
- **Use Case**: Integration with external APIs, CRM systems

### 6. Input Node
- **Purpose**: Collects and validates specific user input
- **Data**:
  ```json
  {
    "type": "input",
    "input_type": "email|phone|number|date|text",
    "variable_name": "user_email",
    "validation_pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
  }
  ```
- **Input Types**:
  - `email`: Email address validation
  - `phone`: Phone number validation
  - `number`: Numeric input
  - `date`: Date input
  - `text`: Free text input
- **Use Case**: Contact forms, data collection

### 7. End Node
- **Purpose**: Terminates the conversation
- **Data**:
  ```json
  {
    "type": "end",
    "content": "Thank you for using our service!"
  }
  ```
- **Use Case**: Conversation endings, thank you messages

## Quick Reply Buttons

Message nodes can include quick reply buttons that appear as clickable options in Telegram:

```json
{
  "type": "message",
  "content": "What service do you need?",
  "quick_replies": ["Windows Installation", "Linux Installation", "Support"]
}
```

## Variable Interpolation

You can use variables in message content and webhook data:

```json
{
  "type": "message",
  "content": "Hello {{user_name}}! Your order {{order_id}} is ready."
}
```

## Example Flow Structure

```
Start → Welcome Message (with buttons)
  ↓
Condition Node (check user input)
  ↓
Services Response (if "services" mentioned)
  ↓
End Node
```

## Best Practices

1. **Always start with a Start node**
2. **Use Message nodes for user communication**
3. **Use Condition nodes for branching logic**
4. **Include quick reply buttons for better UX**
5. **Use variables to personalize responses**
6. **Test your flows thoroughly** 