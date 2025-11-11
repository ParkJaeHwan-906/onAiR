def simple_generate_answer(query, contexts):
    bullets = []
    for c in contexts:
        sec = c["source"].get("section")
        p = c["source"].get("pages")
        snippet = c["source"]["content"][:200]
        bullets.append(f"- [{sec} p{p}] {snippet}...")
    return (
        f"질문: {query}\n\n"
        "관련 문서 근거:\n" + "\n".join(bullets) +
        "\n\n(임시 답변입니다. Step 6에서 LLM 기반 생성기로 교체)"
    )
