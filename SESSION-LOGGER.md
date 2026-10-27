# SESSION-LOGGER — Continuous logging

The session logger captures every exchange into the timeline (ground truth), extracts facts,
and writes them through the gate into the store. In OpenClaw it runs as a post-response
sub-agent; standalone it's just `Brain.log_exchange`.

## Flow

```
user msg ─▶ agent reply ─▶ Brain.log_exchange(user, agent, session_id)
   │                              │
   │                              ├─▶ Timeline.append(user_msg)   # redacted on write
   │                              ├─▶ Timeline.append(agent_resp)
   │                              ├─▶ extract_facts()             # pattern-based, zero-LLM
   │                              ├─▶ Timeline.append(extract)
   │                              └─▶ Brain.remember(each fact)   # AdmissionGate guards it
```

## Guarantees (CODE, tested)

- **Redaction on every write.** Secrets never hit the timeline; the original SHA-256 is kept.
- **Append-only.** Events are immutable; one JSONL file per day; a `LATEST` pointer.
- **File-locked.** Concurrent sub-agents won't interleave a line (POSIX `flock`, copy fallback).
- **Extraction is honest.** `extract_facts` uses hardened regex (it catches "Ch101 … 72/80").
  If it extracts nothing, nothing is claimed.

## What it does NOT do

- It does not send notifications. The **digest** does that, via explicit notifiers
  (`ConsoleNotifier` prints; `WebhookNotifier` performs a real HTTP POST). No print pretends to
  be a delivered DM.
