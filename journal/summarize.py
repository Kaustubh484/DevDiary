# journal/summarize.py
from __future__ import annotations

import json
import re
from typing import Dict, Any, Optional, List

from ollama import Client
from .cache import (
    load_cache,
    purge_bad_entries,
    save_cache,
    get_cached,
    put_cached,
)

client = Client()
def _chat(system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
    kwargs = {
        "model": "llama3",
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()},
        ],
    }
    if json_mode:
        kwargs["format"] = "json"
    resp = client.chat(**kwargs)
    return resp["message"]["content"].strip()


# -------------------------
# Time window phrase (fixed grammar & capitalization)
# -------------------------
def _time_window_phrase(mode: str, since_date: str, to_date: Optional[str]) -> str:
    m = (mode or "").lower()
    if m == "today":
        return "Today"
    if m == "weekly":
        return "In the last 7 days"
    if m == "monthly":
        return "In the last month"
    if (m.startswith("custom") or m == "custom") and since_date:
        if to_date:
            return f"From {since_date} to {to_date}"
        return f"Since {since_date}"
    return f"Since {since_date}" if since_date else "Recently"


# -------------------------
# Robust JSON parsing helpers
# -------------------------
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

def _strip_code_fences(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()

def _normalize_quotes(text: str) -> str:
    return (
        text.replace("“", "\"").replace("”", "\"")
            .replace("‘", "'").replace("’", "'")
    )

def _extract_json_block(text: str) -> Optional[str]:
    text = _strip_code_fences(_normalize_quotes(text))
    m = _JSON_OBJECT_RE.search(text)
    if not m:
        return None
    return text[m.start():m.end()]

def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    # 1) direct
    try:
        return json.loads(text)
    except Exception:
        pass

    # 2) find a {...} block inside noise
    block = _extract_json_block(text)
    if block:
        try:
            return json.loads(block)
        except Exception:
            # 3) remove trailing commas before } or ]
            cleaned = re.sub(r",\s*([}\]])", r"\1", block)
            try:
                return json.loads(cleaned)
            except Exception:
                return None
    return None


# -------------------------
# Commit parsing & heuristics
# -------------------------
def _extract_commit_hash(block: str) -> Optional[str]:
    # First line of each block is "abcd123 Message..."
    first = block.strip().splitlines()[0] if block.strip() else ""
    m = re.match(r"^([0-9a-f]{6,40})\b", first)
    return m.group(1) if m else None

def _extract_commit_message(block: str) -> str:
    first = block.strip().splitlines()[0] if block.strip() else ""
    parts = first.split(maxsplit=1)
    return parts[1] if len(parts) > 1 else ""

def _heuristic_work_type(msg: str) -> str:
    msg_l = msg.lower()
    if any(k in msg_l for k in ("fix", "bug", "hotfix", "patch")):
        return "bugfix"
    if any(k in msg_l for k in ("feat", "feature", "add", "implement")):
        return "feature"
    if any(k in msg_l for k in ("refactor", "cleanup", "restructure")):
        return "refactor"
    if any(k in msg_l for k in ("doc", "readme", "changelog")):
        return "docs"
    if any(k in msg_l for k in ("test", "spec", "unit test", "unittest")):
        return "test"
    if any(k in msg_l for k in ("perf", "optimiz")):
        return "perf"
    if any(k in msg_l for k in ("build", "packag")):
        return "build"
    if any(k in msg_l for k in ("ci", "pipeline", "workflow")):
        return "ci"
    if any(k in msg_l for k in ("chore", "deps", "dependency", "bump")):
        return "chore"
    return "other"


# -------------------------
# Main per-commit classifier/summarizer (with cache)
# -------------------------
def classify_and_summarize_commit(
    commit_block: str,
    repo_name: str,
    since_date: str,
    to_date: Optional[str],
    mode: str,
    cache_path=None,
) -> Dict[str, Any]:
    """
    Returns dict:
      {
        "commit_hash": "...",
        "work_type": "feature|bugfix|refactor|docs|test|chore|perf|build|ci|other",
        "bullet": "- `abc123`: ...",
        "team_snippet": "short phrase"
      }
    """
    commit_hash = _extract_commit_hash(commit_block) or "unknown"
    commit_msg  = _extract_commit_message(commit_block)

    cache = load_cache() if cache_path is None else load_cache(cache_path)
    # auto-heal bad cached entries like "(summary unavailable) ..."
    cache = purge_bad_entries(cache)
    save_cache(cache)

    cached = get_cached(commit_hash, cache)
    if cached:
        return cached

    time_window = _time_window_phrase(mode, since_date, to_date)

    system_prompt = f"""
        You are a developer journal assistant. Convert a single Git commit (header, files, and a --stat diff)
        into a JSON object with: commit_hash, work_type, bullet, team_snippet.

        Rules:
        - work_type MUST be one of: feature, bugfix, refactor, docs, test, chore, perf, build, ci, other.
        - bullet MUST be a single bullet string like:
        - `abc123`: Clear one-sentence summary (key files)
        Include the work type at the start in square brackets, e.g. "- [feature] `abc123`: ...".
        - team_snippet MUST be a short phrase that can be aggregated across repos (no trailing punctuation).
        - Use this time window phrase in your reasoning if needed: "{time_window}".

        Respond with ONLY JSON (no prose), no code fences.
        """.strip()

    # We pass the raw block (header + files + optional --stat) as-is
    user_prompt = f"""
        Repository: {repo_name}
        Time Window: {time_window}

        Raw Commit Block:
        {commit_block}

        Return JSON ONLY with:
        {{
        "commit_hash": "{commit_hash}",
        "work_type": "feature|bugfix|refactor|docs|test|chore|perf|build|ci|other",
        "bullet": "- [<work_type>] `{commit_hash}`: <one-sentence summary> (files)",
        "team_snippet": "<short phrase for cross-repo summary>"
        }}
        """.strip()

    # 1) Ask in JSON mode
    try:
        resp = client.chat(
            model="llama3",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",  "content": user_prompt},
            ],
            format="json",  # ask for strict JSON
        )
        content = resp["message"]["content"]
        data = _try_parse_json(content)

        # 2) Retry once without format if parsing failed
        if not data:
            resp2 = client.chat(
                model="llama3",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",  "content": user_prompt},
                ],
            )
            data = _try_parse_json(resp2["message"]["content"])

        # 3) Final deterministic fallback (heuristics)
        if not data:
            wt = _heuristic_work_type(commit_msg)
            data = {
                "commit_hash": commit_hash,
                "work_type": wt,
                "bullet": f"- [{wt}] `{commit_hash}`: {commit_msg or 'Updated files'}",
                "team_snippet": (commit_msg or "updates")[:60].rstrip("."),
            }

        # sanitize & defaults
        if "commit_hash" not in data or not data["commit_hash"]:
            data["commit_hash"] = commit_hash
        if "work_type" not in data or not data["work_type"]:
            data["work_type"] = _heuristic_work_type(commit_msg)
        if "bullet" not in data or not data["bullet"]:
            data["bullet"] = f"- [{data['work_type']}] `{commit_hash}`: {commit_msg or 'Updated files'}"
        if "team_snippet" not in data or not data["team_snippet"]:
            data["team_snippet"] = (commit_msg or "updates")[:60].rstrip(".")

        # cache only normalized dicts
        put_cached(commit_hash, data, cache)
        save_cache(cache)
        return data

    except Exception as e:
        fallback = {
            "commit_hash": commit_hash,
            "work_type": _heuristic_work_type(commit_msg),
            "bullet": f"- `[{_heuristic_work_type(commit_msg)}] {commit_hash}`: (summary unavailable) {str(e)}",
            "team_snippet": "updates",
        }
        put_cached(commit_hash, fallback, cache)
        save_cache(cache)
        return fallback

def generate_repo_standup_paragraph(repo_name: str, time_window: str, bullets: list[str], team_snips: list[str]) -> str:
    """
    Ask the LLM for a short, natural standup paragraph for ONE repo.
    Falls back to rule-based if the model fails for any reason.
    """
    if not bullets:
        return ""

    # Keep it short: pass only the first ~10 bullets to avoid verbosity
    bullets_text = "\n".join(bullets[:10])

    system_prompt = """
        You are a developer journal assistant.
        Given a list of commit bullets from a single repository, write a concise
        standup update as if the developer is speaking. 2–3 sentences, natural tone.
        Avoid file paths, hashes, and jargon; group similar work together.
        """
    user_prompt = f"""
        Repository: {repo_name}
        Time window: {time_window}

        Bullets:
        {bullets_text}

        Write a 2–3 sentence standup paragraph. No preface, no headers.
        """

    try:
        paragraph = _chat(system_prompt, user_prompt)
        # minimal sanity check
        if len(paragraph.split()) < 8:
            raise ValueError("Too short")
        return paragraph
    except Exception:
        # fallback: rule-based
        short = ", ".join(sorted(set(team_snips))) if team_snips else "progress across multiple areas"
        return f"{time_window}, I focused on {short}. I wrapped up key changes and ensured things are stable."



def generate_team_scrum_paragraph(repo_summaries: list[Dict[str, Any]], since_date: str, to_date: Optional[str], mode: str) -> str:
    """
    Given multiple repo-level summaries (each contains 'repo_name' and 'standup_summary'),
    produce a cohesive, 2–3 sentence team-level scrum summary paragraph.
    """
    time_window = _time_window_phrase(mode, since_date, to_date)
    if not repo_summaries:
        return ""

    lines = []
    for r in repo_summaries:
        para = (r.get("standup_summary") or "").strip()
        if para:
            lines.append(f"{r['repo_name']}: {para}")

    joined = "\n".join(lines[:8])  # cap for brevity

    system_prompt = """
        You are a Scrum Master assistant.
        Given several repo-level standup paragraphs, write ONE concise summary (2–3 sentences).
        Sound natural, avoid repetition, and highlight themes (features, fixes, refactors).
        Do not use headings. No bullet points. Just a short paragraph.
        """
    user_prompt = f"""
        Time Window: {time_window}

        Repo updates:
        {joined}

        Write one 2–3 sentence team summary.
        """

    try:
        paragraph = _chat(system_prompt, user_prompt)
        if len(paragraph.split()) < 10:
            raise ValueError("Too short")
        return paragraph
    except Exception:
        # fallback: join repo names
        names = ", ".join([r["repo_name"] for r in repo_summaries])
        return f"{time_window}, the team advanced work across {names}, making steady progress on features, fixes, and cleanup."

# -------------------------
# Summarize entire repo text (multi-commit)



# -------------------------
def summarize_repo_text_block(
    repo_name: str,
    since_date: str,
    to_date: Optional[str],
    mode: str,
    full_repo_block_text: str,
) -> Dict[str, Any]:
    """
    Takes the FULL raw text for a repo (multiple commits, separated by '===COMMIT==='),
    runs per-commit classification & summary (with cache), and returns:
      {
        "repo_name": repo_name,
        "bullets": [ "...", ... ],
        "team_snippets": [ "...", ... ],
        "standup_summary": "<ready-to-speak paragraph>"
      }
    """
    time_window = _time_window_phrase(mode, since_date, to_date)

    blocks: List[str] = [
        b.strip() for b in full_repo_block_text.split("===COMMIT===") if b.strip()
    ]

    per_commit = [
        classify_and_summarize_commit(b, repo_name, since_date, to_date, mode)
        for b in blocks
    ]

    bullets = [x["bullet"] for x in per_commit if x.get("bullet")]
    team_snips = [x["team_snippet"] for x in per_commit if x.get("team_snippet")]

    # NEW: ask LLM for a natural paragraph
    standup_paragraph = generate_repo_standup_paragraph(repo_name, time_window, bullets, team_snips)

    return {
        "repo_name": repo_name,
        "bullets": bullets,
        "team_snippets": team_snips,
        "standup_summary": standup_paragraph,
    }
    
    
    
