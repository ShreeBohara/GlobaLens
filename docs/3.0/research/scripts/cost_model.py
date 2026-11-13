D = 30.4  # days/month
# ---------- Embeddings ----------
TOK_PER_ART = 120  # title + lede, embedding-tokenizer tokens (assumption)
print("EMBEDDINGS (title+lede, 120 tok/article)")
for arts in (100_000, 300_000):
    tok_m = arts * TOK_PER_ART * D / 1e6
    print(f"  {arts:,}/day -> {tok_m:,.0f}M tok/mo | OpenAI 3-small $0.02: ${tok_m*0.02:,.1f} | "
          f"Gemini-001 std $0.15: ${tok_m*0.15:,.0f} batch $0.075: ${tok_m*0.075:,.0f}")
# Modal L4 GPU micro-batching (cold-start dominated) estimate
L4_H = 0.000222 * 3600
for runs_per_day, secs_per_run in ((96, 60), (24, 85), (1, 600)):
    h = runs_per_day * secs_per_run * D / 3600
    print(f"  Modal L4 {runs_per_day} runs/day x {secs_per_run}s -> {h:,.1f} GPU-h/mo -> ${h*L4_H:,.1f} (L4 ${L4_H:.2f}/h)")

# ---------- LLM summarization ----------
P, V, O = 1500, 1800, 350   # cached prefix, variable input, output tokens per story
print("\nSUMMARIES (prefix 1.5k cached, 1.8k variable in, 350 out, thinking off)")
def haiku(stories_per_day, batch, hit):
    n = stories_per_day * D
    base_in = 0.10 * (0.5 if batch else 1)
    out = 0.50 * (0.5 if batch else 1)
    read = 0.1 * base_in
    pref = n * P / 1e6 * (hit * read + (1 - hit) * base_in)
    var = n * V / 1e6 * base_in
    o = n * O / 1e6 * out
    return pref + var + o
for s in (2000, 5000):
    print(f"  {s:,}/day Haiku 5.5 std (95% cache): ${haiku(s,False,0.95):,.1f} | "
          f"batch 0%/50%/90% hit: ${haiku(s,True,0.0):,.1f} / ${haiku(s,True,0.5):,.1f} / ${haiku(s,True,0.9):,.1f}")
    # token-inflation sensitivity (+40% tokens for non-Latin scripts / new tokenizer)
    print(f"      +40% tokens sensitivity (batch, 50% hit): ${haiku(s,True,0.5)*1.4:,.1f}")
    # Sonnet 5.5 batch for comparison (same token profile)
    n = s * D
    son = n*(P+V)/1e6*1.0 + n*O/1e6*5.0
    print(f"      Sonnet 5.5 batch (no cache): ${son:,.0f}")

# Open model on rented GPU (gpt-oss-20b on Modal L4 via vLLM) - throughput ASSUMPTIONS
PREFILL_TPS, DECODE_TPS, REASON_TOK = 4500, 900, 150
for s in (2000, 5000):
    in_tok = s * (V + 0.2 * P)       # vLLM automatic prefix caching ~80% of shared prefix
    out_tok = s * (O + REASON_TOK)
    gpu_h_day = in_tok / PREFILL_TPS / 3600 + out_tok / DECODE_TPS / 3600
    load_h_day = 24 * 90 / 3600     # hourly batches, ~90s model load/warmup each
    for label, h in (("compute only", gpu_h_day), ("+hourly cold starts", gpu_h_day + load_h_day)):
        print(f"  {s:,}/day gpt-oss-20b on Modal L4 [{label}]: {h*D:,.1f} GPU-h/mo -> ${h*D*L4_H:,.1f}")

# Agent Q&A per question
for name, pin, pout in (("Haiku 5.5", 0.10, 0.50), ("Sonnet 5.5", 2.0, 10.0)):
    cost = 20_000/1e6*pin + 1_200/1e6*pout
    print(f"\nAgent question ({name}, ~20k in / 1.2k out, uncached): ${cost:.4f}/q -> 3,000 q/mo ${cost*3000:,.1f}")
