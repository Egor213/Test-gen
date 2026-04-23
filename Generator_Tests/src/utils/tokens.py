import tiktoken

CUSTOM_MODEL_MAP = {
    "qwen/qwen3-8b": "cl100k_base",
}


def count_tokens(prompt: dict | str, model_name: str = "gpt-3.5-turbo") -> int:
    encoding_name = CUSTOM_MODEL_MAP.get(model_name)
    if encoding_name is not None:
        encoding = tiktoken.get_encoding(encoding_name)
    else:
        try:
            encoding = tiktoken.encoding_for_model(model_name)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
    if isinstance(prompt, dict):
        prompt = " ".join(prompt.values())
    return len(encoding.encode(prompt))
