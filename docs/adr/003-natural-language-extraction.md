# ADR-003: Natural Language Parameter Extraction Architecture

## Status
Accepted

## Context
The MCP server needs to intelligently extract search parameters from natural language user queries such as "Python events near me today" or "remote data science meetups this week". This requires parsing temporal references, location indicators, topic keywords, and event preferences from unstructured text.

## Decision
We will implement a rule-based natural language processing system using regular expressions and keyword matching, with a structured extraction pipeline that converts user queries into typed `EventQuery` objects.

## Rationale

### Alternatives Considered:

1. **Full NLP Library (spaCy/NLTK)**
   - Pros: More sophisticated parsing, entity recognition
   - Cons: Large dependencies, complexity, overkill for domain-specific queries

2. **LLM-based Extraction (Claude/GPT)**
   - Pros: Highly flexible, natural understanding
   - Cons: API costs, latency, dependency on external service

3. **Rule-based Regex System**
   - Pros: Fast, predictable, no external dependencies, domain-specific
   - Cons: Limited flexibility, requires manual pattern definition

4. **Hybrid Approach**
   - Pros: Best of both worlds
   - Cons: Increased complexity

## Decision Rationale

### Why Rule-based System:

1. **Performance**: Regex parsing is extremely fast and has no network overhead
2. **Predictability**: Deterministic behavior makes debugging and testing easier
3. **Domain-specific**: Meetup event queries follow predictable patterns
4. **No Dependencies**: Reduces external API dependencies and costs
5. **Offline Operation**: Works without internet connectivity
6. **Transparency**: Clear understanding of what patterns are matched

### Implementation Strategy:

```python
def extract_query_parameters(self, user_prompt: str) -> EventQuery:
    """Extract structured parameters from natural language."""
    query = EventQuery()
    prompt_lower = user_prompt.lower()
    
    # Time extraction patterns
    time_patterns = {
        r'\btoday\b': lambda: datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
        r'\btomorrow\b': lambda: datetime.now() + timedelta(days=1),
        r'\bthis week\b': lambda: datetime.now(),
        r'\bnext week\b': lambda: datetime.now() + timedelta(weeks=1),
        r'\bin (\d+) hour[s]?\b': lambda m: datetime.now() + timedelta(hours=int(m.group(1))),
        r'\bin (\d+) day[s]?\b': lambda m: datetime.now() + timedelta(days=int(m.group(1)))
    }
    
    # Location extraction patterns
    location_patterns = [
        r'\bnear me\b',
        r'\bin ([A-Za-z\s,]+?)(?:\s|$)',
        r'\bat ([A-Za-z\s,]+?)(?:\s|$)',
    ]
    
    # Topic keyword matching
    tech_keywords = [
        'programming', 'coding', 'software', 'tech', 'python', 'javascript',
        'data science', 'machine learning', 'ai', 'web development'
    ]
    
    # Remote/online indicators
    remote_indicators = ['remote', 'online', 'virtual']
```

## Architecture Components

### 1. Pattern Matching System:
- **Time Patterns**: Regex patterns for relative time expressions
- **Location Patterns**: Geographic and proximity indicators
- **Topic Keywords**: Domain-specific keyword lists
- **Event Type Patterns**: Remote, free, size preferences

### 2. Extraction Pipeline:
1. **Normalization**: Convert to lowercase, clean text
2. **Time Extraction**: Parse temporal references into datetime objects
3. **Location Extraction**: Identify geographic constraints
4. **Topic Extraction**: Match relevant keywords and interests
5. **Preference Extraction**: Identify event type preferences
6. **Validation**: Ensure extracted parameters are reasonable

### 3. Extensibility Mechanisms:
- **Keyword Lists**: Easy to extend with new topics and domains
- **Pattern Registry**: Modular pattern addition
- **Custom Extractors**: Plugin system for specialized extraction logic

## Benefits

### Immediate:
- Fast execution (microseconds vs seconds for LLM calls)
- No API costs or rate limits
- Predictable and debuggable behavior
- Works offline
- Easy to extend with new patterns

### Long-term:
- Foundation for more sophisticated NLP if needed
- Clear separation of concerns
- Testable and maintainable
- Performance monitoring is straightforward

## Limitations and Mitigations

### Limitations:
1. **Limited Flexibility**: Can't handle novel phrasings
2. **Manual Pattern Maintenance**: New patterns require code updates
3. **No Context Understanding**: Limited semantic understanding
4. **False Positives**: Regex can match unintended patterns

### Mitigations:
1. **Comprehensive Pattern Coverage**: Build extensive pattern library based on common use cases
2. **Fallback Handling**: Graceful degradation when extraction fails
3. **User Feedback**: Log extraction failures to improve patterns
4. **Hybrid Future**: Architecture supports adding LLM extraction later
5. **Testing**: Extensive test coverage for pattern matching

## Success Metrics

### Extraction Accuracy:
- Percentage of queries with successful time extraction
- Percentage of queries with successful location extraction
- Percentage of queries with relevant topic extraction

### User Experience:
- User satisfaction with search results
- Frequency of "no results found" responses
- User query patterns and common failures

### Performance:
- Average extraction time (target: <1ms)
- Memory usage during extraction
- Pattern matching success rates

## Future Evolution Path

### Phase 1 (Current): Rule-based System
- Comprehensive regex patterns
- Keyword matching
- Basic validation

### Phase 2 (Future): Enhanced Patterns
- Machine learning for keyword expansion
- Sentiment analysis for event preferences
- Location geocoding integration

### Phase 3 (Future): Hybrid Approach
- LLM extraction for complex queries
- Rule-based system for common patterns
- Intelligent routing between approaches

## Implementation Details

### Error Handling:
```python
try:
    if match.groups():
        query.start_time = time_func(match)
    else:
        query.start_time = time_func()
    break
except Exception as e:
    logging.warning(f"Error parsing time pattern {pattern}: {e}")
```

### Extensibility:
```python
# Easy to add new patterns
tech_keywords.extend(['rust', 'go', 'kubernetes', 'docker'])

# Custom extraction functions
def extract_experience_level(prompt: str) -> Optional[str]:
    if 'beginner' in prompt.lower():
        return 'beginner'
    # ... more logic
```

## Testing Strategy

### Unit Tests:
- Test each pattern type individually
- Test edge cases and boundary conditions
- Test pattern combinations

### Integration Tests:
- Test complete extraction pipeline
- Test with real user queries
- Test failure modes and recovery

### Performance Tests:
- Benchmark extraction speed
- Memory usage profiling
- Scalability testing

---

**Date**: 2025-07-27  
**Author**: Dan Shields  
**Dependencies**: ADR-002 (Dual API Strategy)
