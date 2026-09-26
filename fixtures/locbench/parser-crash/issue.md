parse_tokens raises ValueError when the config line contains no equals sign.
It should return an empty mapping instead of crashing the tokenizer pipeline.
