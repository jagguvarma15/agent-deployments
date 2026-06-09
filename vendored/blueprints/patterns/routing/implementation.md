# Routing — Implementation

## Core Interfaces

```
Classification:
  route: string
  confidence: float
  entities: map of string → any

Route:
  name: string
  description: string
  handler: function(input, entities) → response

RoutingConfig:
  classifier_prompt: string
  routes: list of Route
  fallback: Route
  confidence_threshold: float          // Default: 0.7
  classifier_model: string             // Can be cheaper than handler models
```

## Core Pseudocode

### route_and_handle

```
function route_and_handle(input, config):
  // Classify
  classification = classify(input, config)

  // Check confidence
  if classification.confidence < config.confidence_threshold:
    return config.fallback.handler(input, {})

  // Find route
  route = find_route(classification.route, config.routes)
  if route == null:
    return config.fallback.handler(input, classification.entities)

  // Handle
  return route.handler(input, classification.entities)
```

### classify

```
function classify(input, config):
  route_descriptions = ""
  for route in config.routes:
    route_descriptions += "- " + route.name + ": " + route.description + "\n"

  response = call_llm(
    system: config.classifier_prompt,
    message: "Available routes:\n" + route_descriptions +
             "\n\nClassify this input:\n" + input +
             "\n\nReturn JSON: {\"route\": \"...\", \"confidence\": 0.0-1.0, \"entities\": {}}"
  )
  return parse_json(response.text)
```

### find_route

```
function find_route(route_name, routes):
  for route in routes:
    if route.name == route_name:
      return route
  return null
```

## State Management

Routing is stateless per call. The classifier runs once per input. State is maintained by individual handlers if needed.

## Prompt Engineering Notes

### Classifier Prompt
```
System:
You classify user inputs into predefined routes.
Consider the intent and content of the input.
Return the most appropriate route with your confidence level.
If the input doesn't clearly match any route, use a low confidence score.
Extract relevant entities (names, IDs, amounts) when present.
```

### Handler Prompts
Each handler gets a focused system prompt:
```
// Technical handler:
System: You are a technical support specialist. Help with code, debugging, and technical questions.

// Billing handler:
System: You handle billing inquiries. You can look up accounts and process refunds.
```

## Prompt Templates

These are production-ready templates. Copy and adapt — replace `{placeholders}` with your specifics.

### Classifier system prompt

```
You classify user messages into predefined routes.

Available routes:
- {route_name_1}: {one_sentence_description — what types of messages belong here}
- {route_name_2}: {one_sentence_description}
- {route_name_N}: {one_sentence_description}

Rules:
- Select exactly one route from the list above.
- Do not invent route names. Use only the names listed.
- Assign the route that best matches the user's primary intent, not surface keywords.
- If the message is ambiguous or does not clearly match any route, select "{fallback_route_name}" and set confidence below 0.6.

Respond with a JSON object only — no text before or after:
{"route": "{selected_route_name}", "confidence": {0.0-1.0}, "reason": "{one_sentence_explanation}"}
```

### Classifier user message

```
{user_message}
```

### Handler system prompt template

```
You are a specialist handling {route_name} inquiries.

Your role: {what_this_handler_does}
Your scope: {what_is_in_scope — be explicit}
Out of scope: {what_to_decline_or_escalate}

{any_domain_specific_instructions — e.g. "Always verify account status before discussing charges."}
```

### Low-confidence fallback message (when confidence < threshold)

```
I want to make sure I connect you with the right person.

Could you tell me more about what you need help with? For example:
- {example_1 for route_1}
- {example_2 for route_2}
```

### Customization guide

| Placeholder | What to put here |
|---|---|
| `{route_name}: {description}` | Descriptions must be mutually exclusive — use exclusion language if routes overlap |
| `{fallback_route_name}` | Set this to your catch-all route name — must match exactly |
| `{confidence}` | Use the score to decide: above 0.7 dispatch directly, 0.5-0.7 may clarify, below 0.5 use fallback |
| `{out_of_scope}` | Explicit scope limits prevent handlers from attempting tasks outside their design |

## Testing Strategy

- **Classifier tests:** Known inputs → verify correct route and reasonable confidence
- **Threshold tests:** Ambiguous inputs → verify fallback is triggered
- **Handler tests:** Test each handler independently with route-specific inputs
- **Integration tests:** End-to-end input → classification → handler → response

## Common Pitfalls

- **Threshold too low:** Misrouted inputs degrade quality. Fix: start at 0.8, lower based on data.
- **Overlapping routes:** Similar descriptions confuse classifier. Fix: make route descriptions distinct.
- **Missing routes:** New input types hit fallback too often. Fix: monitor fallback usage, add routes.
- **Classifier cost:** Using expensive model for classification wastes budget. Fix: use cheapest model that achieves acceptable accuracy.
