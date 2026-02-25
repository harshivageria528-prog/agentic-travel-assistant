from langchain_community.chat_models import ChatOllama

def get_llm():
    """
    Returns a lightweight local model via Ollama.
    Uses q2_K quantized TinyLlama (~483MB) for systems with ~2GB available memory.
    """
    llm = ChatOllama(
        model="tinyllama:1.1b-chat-v1-q2_K",
        temperature=0,
        num_ctx=2048,  # Smaller context = less memory
    )
    return llm