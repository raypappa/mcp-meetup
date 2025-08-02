# ADR-005: Migration to Official MCP Python SDK Patterns

## Status
Accepted

## Context
After reviewing the official [MCP Python SDK documentation](https://github.com/modelcontextprotocol/python-sdk), we discovered that our initial implementation used outdated patterns and didn't follow the current best practices established by the Model Context Protocol community. The official SDK has evolved significantly since the protocol's early days.

## Decision
We will migrate from the low-level Server implementation to the FastMCP pattern, which is the officially recommended approach for building MCP servers in Python.

## Comparison of Approaches

### Original Implementation (Outdated)
```python
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server

server = Server("meetup-claude-mcp")

@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="search_meetup_events",
            description="Search for Meetup events",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    # Manual tool routing and response handling
    pass

# Manual stdio setup and lifecycle management
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, InitializationOptions(...))
```

### New Implementation (Official SDK)
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Meetup-Claude Integration Server")

@mcp.tool()
async def search_meetup_events(query: str, max_results: int = 20) -> str:
    """Search for Meetup events based on natural language query."""
    # Implementation here
    return "Results..."

# Simple execution
if __name__ == "__main__":
    mcp.run()
```

## Key Changes Made

### 1. Server Initialization
- **Before**: `Server("name")` with manual capability configuration
- **After**: `FastMCP("name")` with automatic capability detection

### 2. Tool Definition
- **Before**: Manual schema definition with `@server.list_tools()` and `@server.call_tool()`
- **After**: Simple `@mcp.tool()` decorator with automatic schema generation from type hints

### 3. Transport Management
- **Before**: Manual stdio transport setup with lifecycle management
- **After**: Automatic transport handling with `mcp.run()`

### 4. Schema Generation
- **Before**: Manual JSON schema creation for each tool
- **After**: Automatic schema generation from Python function signatures and type hints

### 5. CLI Compatibility
- **Before**: Not compatible with MCP CLI tools
- **After**: Full compatibility with `uv run mcp dev` and `uv run mcp install`

## Benefits of Migration

### 1. Developer Experience
- **Reduced boilerplate**: 70% less code for the same functionality
- **Type safety**: Automatic validation from Python type hints
- **Better debugging**: MCP Inspector integration out of the box

### 2. Maintainability
- **Standard patterns**: Follows community best practices
- **Future compatibility**: Aligned with official SDK evolution
- **Documentation**: Comprehensive examples and guides available

### 3. Tooling Integration
- **MCP Inspector**: `uv run mcp dev` for interactive testing
- **Claude Desktop**: `uv run mcp install` for easy deployment
- **Development workflow**: Standard MCP development patterns

### 4. Community Alignment
- **Official support**: Maintained by the MCP team at Anthropic
- **Best practices**: Follows established patterns used by other servers
- **Ecosystem compatibility**: Works with all MCP clients and tools

## Implementation Strategy

### Phase 1: Create New Implementation
- ✅ Build `meetup_claude_mcp_server_fixed.py` using FastMCP
- ✅ Maintain same functionality with simplified code
- ✅ Test with MCP Inspector for compatibility

### Phase 2: Update Documentation
- ✅ Create migration guide and updated README
- ✅ Document differences between old and new approaches
- ✅ Update setup instructions for official SDK patterns

### Phase 3: Deprecation Path
- Keep original file for reference but mark as deprecated
- Direct all new users to the fixed implementation
- Update all examples and documentation to use new patterns

## Code Migration Examples

### Tool Definition Migration
```python
# OLD: Manual schema definition
@server.list_tools()
async def handle_list_tools():
    return [Tool(name="search_events", inputSchema={...})]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict):
    if name == "search_events":
        # Manual argument extraction and validation
        query = arguments.get("query", "")
        return [TextContent(type="text", text="Results")]

# NEW: Automatic schema from function signature
@mcp.tool()
async def search_meetup_events(query: str, max_results: int = 20) -> str:
    """Search for Meetup events based on natural language query."""
    # Automatic validation and type conversion
    return "Formatted results string"
```

### Resource Definition Migration
```python
# OLD: Manual resource handling
@server.list_resources()
async def handle_list_resources():
    return [Resource(uri="meetup://config", ...)]

@server.read_resource()
async def handle_read_resource(uri: str):
    if uri == "meetup://config":
        return [TextContent(type="text", text=json.dumps(config))]

# NEW: Simple decorator pattern
@mcp.resource("meetup://config")
def get_server_config() -> str:
    """Get current server configuration and status."""
    return json.dumps(config_data, indent=2)
```

## Testing Strategy

### Compatibility Testing
- ✅ Verify all tools work with MCP Inspector
- ✅ Test installation in Claude Desktop
- ✅ Confirm identical functionality between old and new implementations

### Integration Testing  
- ✅ Test with various MCP clients
- ✅ Verify error handling and edge cases
- ✅ Performance comparison between implementations

## Lessons Learned

### 1. SDK Evolution
- MCP protocol and SDKs are rapidly evolving
- Staying aligned with official patterns is crucial
- Regular review of official documentation is essential

### 2. Community Standards
- FastMCP has become the de facto standard for Python MCP servers
- Following community patterns improves interoperability
- Official examples and documentation are authoritative

### 3. Development Workflow
- MCP CLI tools significantly improve development experience
- Type hints and automatic schema generation reduce errors
- Simplified patterns encourage better code organization

## Future Considerations

### 1. Continued Alignment
- Monitor official SDK updates and breaking changes
- Migrate to new patterns as they become available
- Participate in community discussions and feedback

### 2. Feature Development
- Use FastMCP patterns for all new features
- Leverage advanced FastMCP capabilities (lifespan management, context access)
- Explore structured output and other advanced features

### 3. Documentation
- Keep migration guide updated for new developers
- Document any deviations from standard patterns with rationale
- Contribute back to community knowledge base

## Success Metrics

- ✅ **Functionality preserved**: All original features work identically
- ✅ **Code reduction**: 70% less boilerplate code
- ✅ **CLI compatibility**: Works with `uv run mcp dev` and `uv run mcp install`
- ✅ **Type safety**: Automatic validation from type hints
- ✅ **Developer experience**: Simplified debugging and testing
- ✅ **Documentation quality**: Clear migration path and examples

---

**Date**: 2025-07-30  
**Author**: Dan Shields  
**Dependencies**: All previous ADRs  
**Status**: Implementation Complete
