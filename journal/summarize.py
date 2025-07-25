from ollama import Client

client = Client()

#def chunk_text_by_commit(git_log: str) -> list[str]:
#    """Split Git log into blocks based on commits."""
#    blocks = git_log.strip().split("\n\n")
#    return [block.strip() for block in blocks if block.strip()]


def summarize_chunk(chunk: str, repo_name: str = "", date: str = "",mode:str="today") -> str:
    """Summarize a Git commit chunk using Ollama."""
    system_prompt = f"""You are a developer journal assistant.

            Your job is to convert raw Git commit activity into clean, professional journal entries.

            Each bullet point should contain:
            - The commit hash (e.g., `abc123`)
            - A clear one-sentence summary of the commit
            - Key file names in parentheses if possible

            After listing the bullet points, also generate a short summary that a developer could say in a standup meeting. It should summarize the overall work done **{mode}**, using one or two clear, natural-language sentences.

            Be concise and clear. Do NOT include unnecessary headers or commentary.

            Format strictly like this:
            - `abc123`: Implemented JWT authentication and refactored session management (`auth.py`, `session.py`)
            - `def456`: Fixed crash in dashboard rendering logic (`dashboard/views.py`)

            **Standup Summary**: In the last 7 days, I worked on backend auth and fixed a frontend crash.

            Repository: `{repo_name}`
            Date: `{date}`
            """
    user_prompt = f"""Here is the raw commit activity:

        {chunk}

        Now write your summary:"""


    try:
        response = client.chat(
            model='llama3',
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
        )
        return response['message']['content'].strip()
    except Exception as e:
        return f"[Error summarizing chunk: {e}]"


def summarize_git_log(git_log: str, repo_name: str = "", date: str = "",mode:str="today") -> str:
    """Summarize a full Git log string, split by commit blocks."""
    #chunks = chunk_text_by_commit(git_log)
    #summaries = [summarize_chunk(c, repo_name=repo_name, date=date, mode=mode) for c in chunks]
    #return "\n".join(s for s in summaries if s)
    return summarize_chunk(git_log, repo_name=repo_name, date=date, mode=mode)  
