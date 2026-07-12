"""
LoRA / QLoRA fine-tune of a small open student on the grounded distilled pairs.

Produces one adapter per writer (newsletter-writer / broadcast-writer). Each pair
is formatted with the base model's chat template as
  system -> user(prompt) -> assistant(target)
so the student learns our exact format and voice. Deploy the resulting adapter on
Baseten and point the API's TRAINED_* env vars at it.

Usage (needs a GPU; install training/requirements.txt in a separate venv):
  python training/train_writer_lora.py --task newsletter --base Qwen/Qwen2.5-7B-Instruct
  python training/train_writer_lora.py --task broadcast  --base Qwen/Qwen2.5-7B-Instruct --epochs 3
"""
from __future__ import annotations

import argparse
import json
import os

import _bootstrap  # noqa: F401


def _load_pairs(task: str):
    path = os.path.join(_bootstrap.DATA_DIR, f"{task}_pairs.grounded.jsonl")
    if not os.path.exists(path):
        raise SystemExit(f"Missing {path}. Run distill.py then grounding.py for --task {task}.")
    with open(path) as fh:
        return [json.loads(line) for line in fh]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", choices=["newsletter", "broadcast"], required=True)
    ap.add_argument("--base", default="Qwen/Qwen2.5-7B-Instruct",
                    help="student base (e.g. Qwen/Qwen2.5-7B-Instruct, openai/gpt-oss-20b)")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--max-seq", type=int, default=4096)
    ap.add_argument("--qlora", action="store_true", help="4-bit QLoRA (fits a single 24GB GPU)")
    args = ap.parse_args()

    # Imported lazily so the rest of the pipeline runs without the heavy stack.
    import torch
    from datasets import Dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import LoraConfig
    from trl import SFTTrainer, SFTConfig

    pairs = _load_pairs(args.task)
    print(f"{args.task}: {len(pairs)} grounded pairs, base={args.base}")

    tok = AutoTokenizer.from_pretrained(args.base)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    def to_text(rec: dict) -> dict:
        messages = [
            {"role": "system", "content": rec["system"]},
            {"role": "user", "content": rec["prompt"]},
            {"role": "assistant", "content": rec["target"]},
        ]
        return {"text": tok.apply_chat_template(messages, tokenize=False)}

    ds = Dataset.from_list([to_text(p) for p in pairs]).train_test_split(test_size=0.05, seed=7)

    quant = None
    if args.qlora:
        quant = BitsAndBytesConfig(
            load_in_4bit=True, bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
        )
    model = AutoModelForCausalLM.from_pretrained(
        args.base, quantization_config=quant, torch_dtype=torch.bfloat16, device_map="auto",
    )

    peft_cfg = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
    )

    out_dir = os.path.join(_bootstrap.OUT_DIR, f"{args.task}-writer")
    cfg = SFTConfig(
        output_dir=out_dir, num_train_epochs=args.epochs, learning_rate=args.lr,
        per_device_train_batch_size=args.batch, gradient_accumulation_steps=args.grad_accum,
        max_seq_length=args.max_seq, logging_steps=10, save_strategy="epoch",
        bf16=True, gradient_checkpointing=True, warmup_ratio=0.03, lr_scheduler_type="cosine",
        packing=False, dataset_text_field="text",
    )
    trainer = SFTTrainer(model=model, args=cfg, train_dataset=ds["train"],
                         eval_dataset=ds["test"], peft_config=peft_cfg)
    trainer.train()
    trainer.save_model(out_dir)
    tok.save_pretrained(out_dir)
    print(f"Saved adapter -> {out_dir}\nNext: deploy on Baseten, set {args.task.upper()}_MODEL + TRAINED_*.")


if __name__ == "__main__":
    main()
