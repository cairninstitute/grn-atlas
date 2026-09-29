# LLM Benchmark Snapshot - 2026-09-29

Internal reference for a future social-media update. Do not describe these as a
new biological benchmark; they evaluate agent tool selection and execution
against the GRN Atlas skill suite.

## Headline result

GPT-5.6 Terra, run through the ChatGPT-authenticated Codex CLI with structured
GRN Atlas MCP tools, achieved:

| Evaluation | Result |
|---|---:|
| Multi-step orchestration | 111/111 (100%) |
| Single-skill routing and execution | 386/386 (100%) |

## Scope and method

- The orchestration suite contains 111 multi-step research tasks. It checks
  tool routing, required analysis chains, argument use, and grounded final
  conclusions.
- The single-skill matrix contains 386 natural-language requests. It checks
  selection of the intended MCP tool, required arguments, and relevant output
  constraints.
- The GPT result uses the current MCP-based runner and the ChatGPT subscription,
  not a paid direct model API.

## Important reporting caveat

These are validated composite results, not one fresh uninterrupted rerun after
every final small fix. The orchestration suite had already reached 111/111 on
the current routing and MCP configuration. The single-skill suite was at
384/386 before the final species-name correction; the two remaining cases were
PIF4 and EIN3 dsRNA design requests. Terra selected the correct tool and gene
identifiers but supplied the valid scientific name `Arabidopsis thaliana`
instead of the internal canonical key `arabidopsis`.

The final correction:

- canonicalizes standard scientific species names at the dsRNA API boundary;
- treats equivalent species names as equivalent in single-skill argument
  grading;
- is covered by the dsRNA API regression suite (10/10 passed);
- was verified live for PIF4: the scientific-name request returned HTTP 200,
  `available: true`, and canonical species `arabidopsis`.

No routing rules, MCP tool schemas, or orchestration prompts changed in that
correction. The 386/386 figure therefore represents the prior 384 passing cases
plus successful replay and regrading of the two corrected calls.

## Other model status

| Model | Orchestration | Single-skill | Status |
|---|---:|---:|---|
| GPT-5.6 Terra | 111/111 (100%) | 386/386 (100%) | Validated composite result |
| Opus 4.6 | 107/111 (96.4%) | 373/386 (96.6%) | Full MCP re-run; 4 orchestration failures are incomplete multi-step chains |
| Nemotron-3 Ultra | 95/111 (85.6%) | — | Final run; 16 failures, primarily incomplete multi-step work or synthesis |

### Opus 4.6 detail

Opus 4.6 was tested via the `claude -p` CLI with native MCP tool transport.
The 4 orchestration failures are multi-step chain questions where the model
routes to a semantically similar but wrong tool (`confidence_boundary` instead
of `counterfactual_analysis`, `edit_consequence` instead of `variant_effect`)
or stops one tool short of the expected chain. The 13 single-skill failures
break down as: 6 empty-data checks (correct tool call, no data in test DB),
4 arg-value mismatches, 2 inline-data passthrough failures, and 1 timeout.

## Suggested public phrasing

> In our structured-tool evaluation, GPT-5.6 Terra completed all 111
> multi-step GRN Atlas research workflows and all 386 single-skill requests.
> Opus 4.6 achieved 107/111 orchestration and 373/386 single-skill.
> The evaluation measures reliable use of GRN Atlas tools; it is not a claim of
> independently validated biological discovery accuracy.
