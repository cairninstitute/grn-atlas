# GRN Atlas MCP Tools

`grn_atlas_mcp_server.py` exposes the GRN Atlas skill schemas as read-only
stdio MCP tools. It is model-neutral: GPT, Claude/Opus, Nemotron, or another
model can use the same `grn_*` tools when its agent host supports MCP.

## Prerequisites

1. Start the local GRN Atlas backend:

   ```bash
   backend/venv/bin/python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8001
   ```

2. Install the MCP SDK in the environment that starts the server:

   ```bash
   backend/venv/bin/python -m pip install -r .agents/requirements-mcp.txt
   ```

## Generic MCP Client Configuration

Configure an MCP-capable client with this stdio server. Replace
`/absolute/path/to/grn-atlas` with this checkout's path.

```json
{
  "mcpServers": {
    "grn_atlas": {
      "command": "/absolute/path/to/grn-atlas/backend/venv/bin/python",
      "args": [
        "/absolute/path/to/grn-atlas/.agents/mcp/grn_atlas_mcp_server.py"
      ],
      "env": {
        "GRN_MCP_HTTP": "http://127.0.0.1:8001"
      }
    }
  }
}
```

The server dynamically publishes the tool definitions from
`_test_llm_orchestration.py`. Tool calls are read-only and execute the
existing skill scripts against the local backend.

## Model Guidance

The MCP transport does not choose tools for a model. Give the agent these
operational rules in its system or developer prompt:

- Use a `grn_*` tool before answering atlas-specific biological questions.
- Use the most specialized tool first. For example, use
  `grn_pathway_enrichment` for explicit pathway enrichment and
  `grn_enrichment` with `type=trait` for trait association.
- Complete every explicitly requested analysis step. Use returned candidate
  IDs or target lists as input to the next tool.
- For a phenotype-to-ranking workflow, use literature review and grounding,
  then phenotype targeting or candidate triage, then consensus ranking.
- Report an unavailable data layer or empty overlap rather than fabricating a
  follow-up result.

The canonical benchmark prompt is `SYSTEM_PROMPT` in
`.agents/skills/_test_llm_orchestration.py`.

## Opus and Nemotron

OpenRouter and other raw model APIs provide model inference, not an MCP agent
runtime. There are two supported options:

1. Use the existing native function-calling harness for API benchmarks. It
   passes the same schemas and `SYSTEM_PROMPT` directly to GPT, Opus, or
   Nemotron.
2. Use an MCP-capable agent host configured with the stdio server above, then
   select the Opus or Nemotron model in that host. This is the comparable path
   to the Codex/Terra MCP benchmark.

Do not expose the local MCP server over a public network. It is intended for a
trusted local agent and local backend.
