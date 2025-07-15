from llama_cpp import Llama

MODEL_PATH = "/home/skaus/models/mistral-7b-instruct-v0.1.Q4_K_M.gguf"

llm = Llama(
    model_path=MODEL_PATH,
    n_ctx=8000,      # Increase if your model allows
    n_threads=8
)

def chunk_text_by_commit(git_log: str) -> list[str]:
    """Split Git log into blocks based on commits."""
    blocks = git_log.strip().split("\n\n")
    return [block.strip() for block in blocks if block.strip()]

def summarize_chunk(chunk: str) -> str:
    prompt = f"""You are a developer journal assistant.

Your job is to summarize Git commit activity into clear, human-readable journal bullet points.

Here is the commit activity:

{chunk}

 Summarizie the work.Mention file paths and commit hashes.



Summary:"""
    try:
        result = llm(prompt, stop=["</s>"])
        return result["choices"][0]["text"].strip()
    except Exception as e:
        return f"[Error summarizing chunk: {e}]"

def summarize_git_log(git_log: str) -> str:
    chunks = chunk_text_by_commit(git_log)
    summaries = [summarize_chunk(c) for c in chunks]
    return "\n".join(f"- {s}" for s in summaries if s)
